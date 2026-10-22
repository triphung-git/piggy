"""Bounded retries for transient file locks; permanent cleanup errors still fail."""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


def remove_tree(path: Path) -> None:
    for attempt in range(6):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            if not path.exists():
                return
            raise
        except PermissionError:
            if attempt == 5:
                raise
            logger.warning("Temporary directory locked; retry %d: %s", attempt + 1, path)
            time.sleep(0.1 * 2 ** attempt)


@contextmanager
def temporary_directory(*, prefix: str, dir: Path | None = None,
                        on_cleanup: Callable[[Path], None] | None = None,
                        on_cleanup_error: Callable[[Path, Exception], None] | None = None) -> Iterator[Path]:
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=dir))
    failed = False
    try:
        yield path
    except BaseException:
        failed = True
        raise
    finally:
        try:
            if on_cleanup:
                on_cleanup(path)
            remove_tree(path)
        except Exception as exc:
            if on_cleanup_error:
                on_cleanup_error(path, exc)
            if not failed:
                raise
            logger.exception("Cleanup also failed; preserving the original failure: %s", path)
