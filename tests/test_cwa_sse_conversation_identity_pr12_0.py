"""PR12.0 ordinary-text request-bound SSE conversation-identity authority.

Deterministic regression tests for the new identity authority:
consensus semantics, fail-closed states, verbatim promotion, route
de-authority, and zero-retry invariant preservation.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
AUTHORITY = EXT / "service_worker_cwa_sse_conversation_identity.js"
WRITE = EXT / "service_worker_runtime_write.js"
DIAG_CAPTURE = EXT / "service_worker_cwa_identity_capture_diag.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_consensus_js(distinct: list[str], requested: str | None) -> dict:
    """Evaluate _cwaSseIdentityConsensus via node with a minimal shim."""
    source = _source(AUTHORITY)
    start = source.index("function _cwaSseIdentityConsensus(")
    end = source.index("\nfunction _cwaSseIdentityParseRequestBodyIdentity(", start)
    consensus_fn = source[start:end]

    program = (
        consensus_fn
        + f"""
const distinct = {json.dumps(distinct)};
const requested = {json.dumps(requested)};
console.log(JSON.stringify(_cwaSseIdentityConsensus(distinct, requested)));
"""
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(program)
        path = handle.name
    try:
        result = subprocess.run(
            ["node", path],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return json.loads(result.stdout.strip().splitlines()[-1])
    finally:
        os.unlink(path)


def test_authority_module_is_wired_last_in_write_domain() -> None:
    source = _source(WRITE)
    fix_import = 'importScripts("service_worker_cwa_sse_conversation_identity.js");'
    diag_import = 'importScripts("service_worker_cwa_identity_capture_diag.js");'
    assert fix_import in source
    assert diag_import in source
    assert source.index(fix_import) < source.index(diag_import)


def test_authority_wraps_the_fully_assembled_turn() -> None:
    source = _source(AUTHORITY)
    assert "const _cwaSseIdentityPriorExecuteNativeTurn = executeNativeTurn;" in source
    assert "executeNativeTurn = async function _cwaSseIdentityExecuteNativeTurn" in source


def test_authority_never_consults_the_route() -> None:
    source = _source(AUTHORITY)
    assert "conversationIdFromUrl" not in source
    assert "ensureRuntimeTab" not in source


def test_authority_promotes_verbatim_without_transform() -> None:
    source = _source(AUTHORITY)
    assert "conversationId: consensus.conversationId" in source
    assert "replace(" not in source
    assert 'startsWith("WEB:")' not in source
    assert 'slice("WEB:".length)' not in source


def test_authority_maps_through_the_committed_identity_surface() -> None:
    js_source = _source(AUTHORITY)
    assert 'const CWA_SSE_IDENTITY_COMMITTED_IDENTITY_ERROR =\n  "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED";' in js_source

    provider = _source(EXT.parent / "browser_native_provider.py")
    assert 'error.startswith("PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED")' in provider


def test_authority_marks_route_authority_as_diagnostic_only() -> None:
    source = _source(AUTHORITY)
    assert "routeConversationIdentityAuthoritative: false" in source


def test_authority_adds_no_retry_or_submit_path() -> None:
    source = _source(AUTHORITY)
    assert "submitOfficialPageTurn" not in source
    assert "Input.insertText" not in source
    assert "chrome.tabs.create" not in source
    assert "ensureRuntimeTab" not in source
    # Exactly one delegated prior call per turn: the passthrough and the main
    # path are mutually exclusive.
    assert source.count("_cwaSseIdentityPriorExecuteNativeTurn(message)") == 2


def test_authority_fails_closed_on_unresolved_identity() -> None:
    source = _source(AUTHORITY)
    assert ":SSE_IDENTITY_UNRESOLVED" in source
    assert ":SSE_IDENTITY_CONFLICT" in source
    assert ":SSE_REQUEST_IDENTITY_MISMATCH" in source
    assert "CWA_SSE_IDENTITY_COMMITTED_IDENTITY_ERROR" in source


def test_consensus_zero_candidates_fail_closed() -> None:
    result = _run_consensus_js([], None)
    assert result["state"] == "unresolved"
    assert result["conversationId"] is None
    assert result["distinctCount"] == 0


def test_consensus_single_candidate_bare_uuid_is_consensus() -> None:
    result = _run_consensus_js(["6aa0c074-5d4c-83ec-b16d-92e095b71bf9"], None)
    assert result["state"] == "consensus"
    assert result["conversationId"] == "6aa0c074-5d4c-83ec-b16d-92e095b71bf9"


def test_consensus_conflicting_candidates_fail_closed() -> None:
    result = _run_consensus_js(
        [
            "6aa0c074-5d4c-83ec-b16d-92e095b71bf9",
            "bb6929bd-23ad-4aae-a234-9ff2dbfe9bab",
        ],
        None,
    )
    assert result["state"] == "conflict"
    assert result["conversationId"] is None
    assert result["distinctCount"] == 2


def test_consensus_duplicate_identical_records_collapse_to_one() -> None:
    # Deduplication happens via the Set in the production path; consensus
    # receives only DISTINCT values, so duplicates never reach conflict.
    result = _run_consensus_js(["6aa0c074-5d4c-83ec-b16d-92e095b71bf9"], None)
    assert result["state"] == "consensus"


def test_consensus_continuation_mismatch_fails_closed() -> None:
    result = _run_consensus_js(
        ["6aa0c074-5d4c-83ec-b16d-92e095b71bf9"],
        "different-conversation-id",
    )
    assert result["state"] == "request_mismatch"
    assert result["conversationId"] is None


def test_consensus_continuation_match_passes() -> None:
    result = _run_consensus_js(
        ["6aa0c074-5d4c-83ec-b16d-92e095b71bf9"],
        "6aa0c074-5d4c-83ec-b16d-92e095b71bf9",
    )
    assert result["state"] == "consensus"


def test_consensus_namespaced_candidate_is_preserved_verbatim() -> None:
    # If the SSE plane itself ever emitted a namespaced id, the authority must
    # neither strip nor transform it — the canonical plane owns rejection.
    namespaced = "WEB:6aa0c074-5d4c-83ec-b16d-92e095b71bf9"
    result = _run_consensus_js([namespaced], None)
    assert result["state"] == "consensus"
    assert result["conversationId"] == namespaced


def test_authority_ignores_non_ordinary_writes() -> None:
    source = _source(AUTHORITY)
    for flag in (
        "characterizeRichInputSupport",
        "characterizeSafeBrowserResponseStreamingSupport",
        "characterizePostAnswerTailTimingSupport",
        "characterizeEarlyProductCompletionSupport",
        "characterizeProductModelProfileSupport",
    ):
        assert flag in source


def test_authority_records_client_message_id_correlation() -> None:
    source = _source(AUTHORITY)
    assert "userMessageIds" in source
    assert "clientMessageId" in source


def test_authority_never_persists_raw_sse_or_auth_material() -> None:
    source = _source(AUTHORITY)
    assert "cookie" not in source.lower()
    assert "authorization" not in source.lower()
    assert "token_urlsafe" not in source
    # Bounded SSE handling only.
    assert "CWA_SSE_IDENTITY_MAX_SSE_BUFFER_CHARS" in source


def test_authority_has_load_sentinel() -> None:
    source = _source(AUTHORITY)
    assert "cwaSseConversationIdentityLoadedV1" in source


@pytest.mark.parametrize(
    ("distinct", "requested", "expected_state"),
    [
        ([], None, "unresolved"),
        ([], "some-id", "unresolved"),
        (["a"], None, "consensus"),
        (["a", "b"], None, "conflict"),
        (["a"], "a", "consensus"),
        (["a"], "b", "request_mismatch"),
    ],
)
def test_consensus_matrix(
    distinct: list[str], requested: str | None, expected_state: str
) -> None:
    result = _run_consensus_js(distinct, requested)
    assert result["state"] == expected_state
