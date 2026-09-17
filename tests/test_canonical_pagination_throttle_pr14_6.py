from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
CANONICAL = EXT / "service_worker_canonical_read_v2.js"
READ_DOMAIN = EXT / "service_worker_runtime_read.js"


def _source() -> str:
    return CANONICAL.read_text(encoding="utf-8")


def test_active_browser_canonical_read_uses_throttle_safe_v2() -> None:
    read_domain = READ_DOMAIN.read_text(encoding="utf-8")
    source = _source()

    assert 'importScripts("service_worker_canonical_read_v2.js");' in read_domain
    assert "CWA_CANONICAL_THROTTLE_MAX_RETRIES = 3" in source
    assert "CWA_CANONICAL_THROTTLE_BACKOFF_BASE_MS = 250" in source
    assert "CWA_CANONICAL_THROTTLE_BACKOFF_MAX_MS = 4_000" in source
    assert "CWA_CANONICAL_RETRY_AFTER_MAX_MS = 10_000" in source
    assert "CWA_CANONICAL_PAGE_PACE_MS = 75" in source


def test_429_retry_is_bounded_and_preserves_exact_page_url() -> None:
    source = _source()

    assert "response.status === 429 && retryThrottle" in source
    assert 'response.headers.get("retry-after")' in source
    assert 'reasonCode: "CANONICAL_READ_THROTTLE_EXHAUSTED"' in source
    assert "attempt >= throttleMaxRetries" in source
    assert "const pageUrl = currentUrl(cursor);" in source
    assert "const older = await fetchBytes(pageUrl, true, true);" in source
    assert "pages.push(older.payload);" in source


def test_only_idempotent_canonical_reads_receive_retry_and_pacing() -> None:
    source = _source()

    assert (
        "const fetchBytes = async (url, authorizeCurrent = false, retryThrottle = false)"
        in source
    )
    assert "const first = await fetchBytes(currentUrl(), true, true);" in source
    assert "const legacy = await fetchBytes(legacyEndpoint, false, false);" in source
    assert "if (pagePaceMs > 0) await sleep(pagePaceMs);" in source
    assert 'method: "GET"' in source
    assert 'method: "POST"' not in source


def test_throttle_exhaustion_never_claims_partial_history_complete() -> None:
    source = _source()

    exhausted = source.index('reasonCode: "CANONICAL_READ_THROTTLE_EXHAUSTED"')
    merge = source.index("const mergedMessages = [];")
    assert exhausted < merge
    assert "if (older.ok !== true) return older;" in source
    assert (
        "const mergedPayload = { ...first.payload, messages: mergedMessages };"
        in source
    )
