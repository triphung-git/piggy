"""Real process ownership tests: parent exit must not leave a profile locked."""

import subprocess
import sys

import pytest

from tft_studio.core.processes import ProcessTree
from tft_studio.core.tempfiles import remove_tree


def test_process_tree_captures_output():
    with ProcessTree([sys.executable, "-c", "print('owned')"], stdout=subprocess.PIPE) as process:
        output, _ = process.communicate(timeout=10)
        assert process.returncode == 0
    assert output.strip() == b"owned"


def test_process_tree_terminates_on_timeout():
    owner = ProcessTree([sys.executable, "-c", "import time; time.sleep(60)"])
    with pytest.raises(subprocess.TimeoutExpired), owner as process:
        process.wait(timeout=0.05)
    assert owner.process.poll() is not None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows open-file deletion semantics")
def test_exited_parent_does_not_leave_child_profile_locked(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    ready = tmp_path / "ready"
    child = (
        "import pathlib,sys,time; "
        "handle=open(sys.argv[1], 'w'); "
        "pathlib.Path(sys.argv[2]).write_text('ready'); time.sleep(60)"
    )
    parent = (
        "import pathlib,subprocess,sys,time; "
        "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2],sys.argv[3]]); "
        "deadline=time.monotonic()+10\n"
        "while not pathlib.Path(sys.argv[3]).exists():\n"
        " if time.monotonic()>deadline: raise TimeoutError('child not ready')\n"
        " time.sleep(.01)\n"
    )
    with ProcessTree([sys.executable, "-c", parent, child,
                      str(profile / "Account Web Data"), str(ready)]) as process:
        assert process.wait(timeout=15) == 0
        assert ready.exists()
        with pytest.raises(PermissionError):
            (profile / "Account Web Data").unlink()
    # Closing the job still owns descendants after the parent exited.
    remove_tree(profile)
    assert not profile.exists()
