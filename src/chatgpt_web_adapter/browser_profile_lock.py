from __future__ import annotations

import os
import time
from pathlib import Path


class BrowserProfileLock:
    """Cross-process exclusive lock for one Chromium user-data directory."""

    def __init__(self, profile_dir: str | Path, *, timeout: float = 30.0) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        profile = Path(profile_dir)
        self.path = profile.parent / f".{profile.name}.lock"
        self.timeout = float(timeout)
        self._stream = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._stream = stream
                return
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    stream.close()
                    raise TimeoutError(
                        f"Browser profile is busy: {self.path.parent}"
                    )
                time.sleep(0.1)

    def release(self) -> None:
        stream = self._stream
        if stream is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()
            self._stream = None

    def __enter__(self) -> "BrowserProfileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()
