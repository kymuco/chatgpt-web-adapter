from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from .browser_native_provider import BrowserNativeTurnProvider
from .browser_native_protocol import PROTOCOL_VERSION
from .exceptions import RequestError


@dataclass(frozen=True)
class TemporaryChatModeProbeResult:
    """Privacy-safe structural evidence from the PR8.7 no-write probe."""

    probe_context: str
    control_found: bool
    candidate_count: int
    selected_before: bool | None
    selected_after: bool | None
    mode_selection_proven: bool
    selection_action: str
    reason: str
    match_signals: tuple[str, ...]
    selection_proof_signals: tuple[str, ...]
    conversation_write_observed: bool
    tab_was_active: bool
    tab_active_after: bool | None
    tab_activated_during_probe: bool | None
    foreground_activation_observed: bool | None
    probe_tab_closed: bool
    elapsed_ms: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_bool(payload: dict[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    return value if isinstance(value, bool) else None


def _safe_string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        item = item.strip()
        if item:
            result.append(item)
    return tuple(result)


def probe_temporary_chat_mode(
    *,
    provider: BrowserNativeTurnProvider | Any | None = None,
    timeout: float = 30.0,
) -> TemporaryChatModeProbeResult:
    """Characterize the official-page Temporary Chat selector without a chat write.

    The extension opens a dedicated isolated new-chat tab, observes only safe
    structural control/state evidence, attempts one Temporary-mode selection,
    verifies that no conversation POST occurred, and closes the probe tab.

    This function is intentionally research/diagnostic. A successful result is
    evidence for PR8.7 characterization; it does not by itself change the
    production ``temporary_chat`` capability from UNKNOWN to AVAILABLE.
    """

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    bridge = provider or BrowserNativeTurnProvider()
    request_id = str(uuid.uuid4())
    connect_timeout = float(getattr(bridge, "connect_timeout", 3.0))
    response = bridge._rpc(  # noqa: SLF001 - same-package research diagnostic boundary
        {
            "type": "turn",
            "request_id": request_id,
            "conversationId": None,
            "text": None,
            "timeoutMs": int(timeout * 1000),
            "canonicalCompleted": False,
            "canonicalCompletedAtMs": None,
            "probeTemporaryMode": True,
        },
        timeout=float(timeout) + max(0.1, connect_timeout),
    )

    if response.get("protocol") != PROTOCOL_VERSION:
        raise RequestError(
            "BROWSER_NATIVE_PROTOCOL_MISMATCH: invalid Temporary Chat probe response",
            request_stage="temporary_chat_probe",
        )
    if response.get("request_id") != request_id:
        raise RequestError(
            "BROWSER_NATIVE_RESPONSE_MISMATCH",
            request_stage="temporary_chat_probe",
        )
    if not response.get("ok"):
        error = response.get("error") or "TEMPORARY_CHAT_PROBE_FAILED"
        raise RequestError(str(error), request_stage="temporary_chat_probe")
    if response.get("conversationWriteObserved") is True:
        raise RequestError(
            "TEMPORARY_CHAT_PROBE_UNEXPECTED_CONVERSATION_WRITE",
            request_stage="temporary_chat_probe",
        )

    probe_context = response.get("probeContext")
    selection_action = response.get("selectionAction")
    reason = response.get("reason")
    candidate_count = response.get("candidateCount")
    elapsed_ms = response.get("elapsedMs")

    return TemporaryChatModeProbeResult(
        probe_context=probe_context if isinstance(probe_context, str) else "unknown",
        control_found=bool(response.get("controlFound")),
        candidate_count=(
            candidate_count
            if isinstance(candidate_count, int) and not isinstance(candidate_count, bool)
            else 0
        ),
        selected_before=_optional_bool(response, "selectedBefore"),
        selected_after=_optional_bool(response, "selectedAfter"),
        mode_selection_proven=bool(response.get("modeSelectionProven")),
        selection_action=(
            selection_action if isinstance(selection_action, str) else "unknown"
        ),
        reason=reason if isinstance(reason, str) else "TEMPORARY_CHAT_PROBE_UNKNOWN",
        match_signals=_safe_string_tuple(response.get("matchSignals")),
        selection_proof_signals=_safe_string_tuple(
            response.get("selectionProofSignals")
        ),
        conversation_write_observed=bool(response.get("conversationWriteObserved")),
        tab_was_active=bool(response.get("tabWasActive")),
        tab_active_after=_optional_bool(response, "tabActiveAfter"),
        tab_activated_during_probe=_optional_bool(response, "tabActivatedDuringProbe"),
        foreground_activation_observed=_optional_bool(
            response, "foregroundActivationObserved"
        ),
        probe_tab_closed=bool(response.get("probeTabClosed")),
        elapsed_ms=(
            elapsed_ms
            if isinstance(elapsed_ms, int) and not isinstance(elapsed_ms, bool)
            else None
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chatgpt_web_adapter.temporary_chat_probe",
        description=(
            "Run the PR8.7 isolated no-write Temporary Chat selector probe. "
            "The production temporary_chat capability remains UNKNOWN until "
            "the resulting live evidence is reviewed."
        ),
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = probe_temporary_chat_mode(timeout=args.timeout)
    except (RequestError, OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2, ensure_ascii=False))
        return 2

    payload = {"ok": True, **result.to_dict()}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if result.mode_selection_proven else 1


if __name__ == "__main__":
    raise SystemExit(main())
