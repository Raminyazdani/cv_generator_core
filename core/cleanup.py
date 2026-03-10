import os
import shutil
import stat
import subprocess
import time
import uuid
from pathlib import Path


def _clear_readonly_windows(root: Path) -> None:
    # Best-effort: remove "Read-only" attribute recursively (Windows)
    if os.name == "nt":
        try:
            subprocess.run(
                ["attrib", "-R", str(root / "*"), "/S", "/D"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True,
            )
        except Exception:
            pass


def _make_writable(path: str) -> None:
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass


def rmtree_reliable(path: str | os.PathLike, *, attempts: int = 25) -> None:
    """
    Reliably remove a directory tree, with retry logic for Windows file locks.

    Note: This function is available for cleanup but not called automatically
    to preserve generated results. Call manually if needed.
    """
    p = Path(path)

    if not p.exists():
        return

    p = p.resolve()

    try:
        renamed = p.with_name(f"{p.name}.__deleting__{uuid.uuid4().hex}")
        p.rename(renamed)
        p = renamed
    except Exception:
        pass

    def onerror(func, failed_path, exc_info):
        _make_writable(failed_path)
        try:
            func(failed_path)
        except Exception:
            raise

    for i in range(attempts):
        try:
            _clear_readonly_windows(p)
            shutil.rmtree(p, onerror=onerror)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            time.sleep(min(2.0, 0.05 * (2 ** i)))
        except OSError:
            time.sleep(min(2.0, 0.05 * (2 ** i)))

    _clear_readonly_windows(p)
    shutil.rmtree(p, onerror=onerror)
