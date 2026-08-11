from __future__ import annotations

import pytest

from chatgpt_web_adapter.browser_profile_lock import BrowserProfileLock


def test_browser_profile_lock_rejects_concurrent_owner_then_recovers(tmp_path) -> None:
    profile = tmp_path / "profile"
    first = BrowserProfileLock(profile, timeout=1)
    second = BrowserProfileLock(profile, timeout=0.05)

    first.acquire()
    try:
        with pytest.raises(TimeoutError, match="Browser profile is busy"):
            second.acquire()
    finally:
        first.release()

    second.acquire()
    second.release()
