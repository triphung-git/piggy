"""Own subprocess trees, including descendants left behind by an exited parent."""

from __future__ import annotations

import contextlib
import ctypes
import logging
import os
import signal
import subprocess
import sys
from ctypes import wintypes

logger = logging.getLogger(__name__)


class _WindowsJob:
    """Closing this non-inherited handle kills only this job's process tree."""

    def __init__(self):
        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD), ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t), ("active_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("basic", BasicLimits), ("io", IoCounters),
                ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t),
            ]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.SetInformationJobObject.restype = wintypes.BOOL
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.AssignProcessToJobObject.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def resume(self, process):
        """Resume the sole initial thread after assigning the suspended process."""
        class ThreadEntry(ctypes.Structure):
            _fields_ = [
                ("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                ("thread_id", wintypes.DWORD), ("owner_pid", wintypes.DWORD),
                ("base_priority", wintypes.LONG), ("delta_priority", wintypes.LONG),
                ("flags", wintypes.DWORD),
            ]

        self.api.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self.api.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        for name in ("Thread32First", "Thread32Next"):
            function = getattr(self.api, name)
            function.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
            function.restype = wintypes.BOOL
        self.api.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenThread.restype = wintypes.HANDLE
        self.api.ResumeThread.argtypes = [wintypes.HANDLE]
        self.api.ResumeThread.restype = wintypes.DWORD
        snapshot = self.api.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            found = self.api.Thread32First(snapshot, ctypes.byref(entry))
            while found:
                if entry.owner_pid == process.pid:
                    thread = self.api.OpenThread(2, False, entry.thread_id)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if self.api.ResumeThread(thread) == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                    finally:
                        self.api.CloseHandle(thread)
                    return
                found = self.api.Thread32Next(snapshot, ctypes.byref(entry))
            raise RuntimeError("Suspended process has no initial thread")
        finally:
            self.api.CloseHandle(snapshot)

    def close(self):
        if self.handle:
            if not self.api.CloseHandle(self.handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = None


class ProcessTree:
    """Popen owner; call close even after the root process has already exited."""

    def __init__(self, command, **kwargs):
        self.job = _WindowsJob() if sys.platform == "win32" else None
        self.process = None
        try:
            if self.job:
                # Assign before any browser/bootloader code can spawn descendants.
                kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW | 0x4
            else:
                kwargs["start_new_session"] = True
            self.process = subprocess.Popen(command, **kwargs)
            if self.job:
                self.job.assign(self.process)
                self.job.resume(self.process)
        except BaseException:
            if self.process is not None and self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
            if self.job:
                self.job.close()
            raise

    def close(self):
        if self.job:
            self.job.close()
        elif self.process:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.process.pid, signal.SIGKILL)
        if self.process:
            self.process.wait(timeout=5)
            for stream in (self.process.stdout, self.process.stderr, self.process.stdin):
                if stream:
                    stream.close()

    def __enter__(self):
        return self.process

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.close()
        except Exception:
            if exc_type is None:
                raise
            logger.exception("Process tree cleanup also failed; preserving original failure")
