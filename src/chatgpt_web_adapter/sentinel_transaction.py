from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from . import client as client_mod
from .auth import CHAT_URL
from .exceptions import RequestError
from .sentinel_requirements import (
    OBSERVED_PREPARE_RESPONSE_KEYS,
    OBSERVED_PROOFOFWORK_KEYS,
    OBSERVED_SO_KEYS,
    OBSERVED_TURNSTILE_KEYS,
    SENTINEL_FINALIZE_PATH,
    SENTINEL_PREPARE_PATH,
    build_sentinel_prepare_headers,
)
from .web_session import suppress_web_session_debug_trace

SENTINEL_EXPIRY_SAFETY_MARGIN_SECONDS = 5.0


@dataclass(frozen=True, eq=False)
class FinalizedSentinelBundle:
    """Memory-only credentials produced by one successful Sentinel finalize."""

    requirements_token: str = field(repr=False, compare=False)
    proof_token: str = field(repr=False, compare=False)
    turnstile_token: str = field(repr=False, compare=False)
    acquired_monotonic: float
    expires_monotonic: float
    source: str = "two_phase_finalize"

    def is_expired(self, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else float(now)
        return current >= self.expires_monotonic


def _emit_event(
    client: Any,
    callback: Callable[[dict[str, Any]], None] | None,
    event_type: str,
    **payload: Any,
) -> None:
    emitter = getattr(client, "_emit_event", None)
    if callable(emitter):
        emitter(callback, event_type, **payload)
    elif callback is not None:
        callback({"type": event_type, **payload})


def _write_structural_trace(client: Any, kind: str, payload: dict[str, Any]) -> None:
    if getattr(client, "debug_trace_dir", None) is None:
        return
    writer = getattr(client, "_write_debug_trace", None)
    if callable(writer):
        writer(kind, payload)


def _mapping_has_keys(value: Any, expected: tuple[str, ...]) -> bool:
    return isinstance(value, dict) and set(expected).issubset(value.keys())


def _derive_prepare_input(client: Any) -> str | None:
    proof_token = getattr(getattr(client, "auth", None), "proof_token", None)
    if not isinstance(proof_token, list):
        return None
    try:
        return client_mod._get_requirements_token(proof_token)
    except Exception as error:
        raise RequestError(
            "SENTINEL_PREPARE_INPUT_DERIVATION_FAILED: could not derive current "
            "prepare input from supplied browser proof material",
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare_input",
        ) from error


def _take_supplied_turnstile_token(client: Any) -> str:
    auth = getattr(client, "auth", None)
    value = getattr(auth, "turnstile_token", None)
    if not isinstance(value, str) or not value.strip():
        raise RequestError(
            "SENTINEL_TURNSTILE_EVIDENCE_REQUIRED: current two-phase Sentinel "
            "finalize requires legitimate browser-derived Turnstile evidence",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_turnstile_gate",
        )
    auth.turnstile_token = None
    return value.strip()


def _finalize_headers(client: Any) -> dict[str, str]:
    return client._build_headers(
        {
            "accept": "*/*",
            "content-type": "application/json",
            "origin": CHAT_URL.rstrip("/"),
            "referer": CHAT_URL,
            "x-openai-target-path": SENTINEL_FINALIZE_PATH,
            "x-openai-target-route": SENTINEL_FINALIZE_PATH,
        }
    )


def _validate_prepare_response(status: int, data: Any) -> tuple[dict[str, Any], str]:
    if not 200 <= int(status) < 300:
        raise RequestError(
            f"Sentinel prepare rejected: status={status}",
            status_code=int(status),
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )
    if not isinstance(data, dict):
        raise RequestError(
            "Sentinel prepare response expected JSON object",
            status_code=int(status),
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )
    if not set(OBSERVED_PREPARE_RESPONSE_KEYS).issubset(data.keys()):
        raise RequestError(
            "SENTINEL_PREPARE_CONTRACT_DRIFT: observed top-level keys are missing",
            status_code=int(status),
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )
    persona = data.get("persona")
    prepare_token = data.get("prepare_token")
    if not isinstance(persona, str) or not persona.strip():
        raise RequestError(
            "SENTINEL_PREPARE_CONTRACT_DRIFT: persona is missing",
            status_code=int(status),
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )
    if not isinstance(prepare_token, str) or not prepare_token.strip():
        raise RequestError(
            "SENTINEL_PREPARE_CONTRACT_DRIFT: prepare_token is missing",
            status_code=int(status),
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )
    if not _mapping_has_keys(data.get("turnstile"), OBSERVED_TURNSTILE_KEYS):
        raise RequestError(
            "SENTINEL_PREPARE_CONTRACT_DRIFT: turnstile shape changed",
            status_code=int(status),
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )
    if not _mapping_has_keys(data.get("proofofwork"), OBSERVED_PROOFOFWORK_KEYS):
        raise RequestError(
            "SENTINEL_PREPARE_CONTRACT_DRIFT: proofofwork shape changed",
            status_code=int(status),
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )
    if not _mapping_has_keys(data.get("so"), OBSERVED_SO_KEYS):
        raise RequestError(
            "SENTINEL_PREPARE_CONTRACT_DRIFT: so shape changed",
            status_code=int(status),
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )
    return data, prepare_token.strip()


def _validate_finalize_response(
    status: int,
    data: Any,
    *,
    acquired_monotonic: float,
) -> tuple[str, float]:
    if not 200 <= int(status) < 300:
        raise RequestError(
            f"Sentinel finalize rejected: status={status}",
            status_code=int(status),
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_finalize",
        )
    if not isinstance(data, dict):
        raise RequestError(
            "Sentinel finalize response expected JSON object",
            status_code=int(status),
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_finalize",
        )
    if not {"persona", "token", "expire_after", "expire_at"}.issubset(data.keys()):
        raise RequestError(
            "SENTINEL_FINALIZE_CONTRACT_DRIFT: observed response keys are missing",
            status_code=int(status),
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_finalize",
        )
    persona = data.get("persona")
    token = data.get("token")
    expire_after = data.get("expire_after")
    if not isinstance(persona, str) or not persona.strip():
        raise RequestError(
            "SENTINEL_FINALIZE_CONTRACT_DRIFT: persona is missing",
            status_code=int(status),
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_finalize",
        )
    if not isinstance(token, str) or not token.strip():
        raise RequestError(
            "SENTINEL_FINALIZE_CONTRACT_DRIFT: token is missing",
            status_code=int(status),
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_finalize",
        )
    if isinstance(expire_after, bool) or not isinstance(expire_after, (int, float)):
        raise RequestError(
            "SENTINEL_FINALIZE_CONTRACT_DRIFT: expire_after is not numeric",
            status_code=int(status),
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_finalize",
        )
    ttl = float(expire_after)
    if ttl <= SENTINEL_EXPIRY_SAFETY_MARGIN_SECONDS:
        raise RequestError(
            "SENTINEL_FINALIZE_CONTRACT_DRIFT: expire_after is too small",
            status_code=int(status),
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_finalize",
        )
    return (
        token.strip(),
        acquired_monotonic + ttl - SENTINEL_EXPIRY_SAFETY_MARGIN_SECONDS,
    )


def acquire_finalized_sentinel_bundle(
    client: Any,
    *,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> FinalizedSentinelBundle:
    """Acquire one two-phase bundle without Turnstile solving or replay."""

    prepare_payload = {"p": _derive_prepare_input(client)}
    _emit_event(client, on_event, "sentinel_prepare_started")
    with suppress_web_session_debug_trace():
        prepare_status, prepare_data = client._json_request(
            "POST",
            f"{CHAT_URL.rstrip('/')}{SENTINEL_PREPARE_PATH}",
            prepare_payload,
            build_sentinel_prepare_headers(client),
        )
    response, prepare_token = _validate_prepare_response(int(prepare_status), prepare_data)
    turnstile = response["turnstile"]
    proofofwork = response["proofofwork"]
    so = response["so"]
    _write_structural_trace(
        client,
        "sentinel-prepare-live",
        {
            "method": "POST",
            "url": f"{CHAT_URL.rstrip('/')}{SENTINEL_PREPARE_PATH}",
            "response_status": int(prepare_status),
            "response_keys": sorted(str(key) for key in response),
            "prepare_token_present": True,
            "turnstile_required": bool(turnstile.get("required")),
            "proofofwork_required": bool(proofofwork.get("required")),
            "so_required": bool(so.get("required")),
            "raw_request_recorded": False,
            "raw_response_recorded": False,
            "challenge_values_recorded": False,
        },
    )
    _emit_event(
        client,
        on_event,
        "sentinel_prepare_succeeded",
        status_code=int(prepare_status),
        prepare_token_present=True,
        turnstile_required=bool(turnstile.get("required")),
        proofofwork_required=bool(proofofwork.get("required")),
        so_required=bool(so.get("required")),
    )
    if not bool(turnstile.get("required")) or not bool(proofofwork.get("required")):
        raise RequestError(
            "SENTINEL_FINALIZE_POLICY_UNOBSERVED: current finalize challenge "
            "combination has not been live-characterized",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_finalize_policy",
        )

    proof_header = client._build_proof_header({"proofofwork": proofofwork})
    if not isinstance(proof_header, str) or not proof_header.strip():
        raise RequestError(
            "Sentinel proof-of-work generation did not produce evidence",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_proof",
        )
    proof_header = proof_header.strip()
    turnstile_token = _take_supplied_turnstile_token(client)
    _emit_event(
        client,
        on_event,
        "sentinel_challenge_ready",
        proof_present=True,
        turnstile_present=True,
        so_required=bool(so.get("required")),
    )

    finalize_payload = {
        "prepare_token": prepare_token,
        "proofofwork": proof_header,
        "turnstile": turnstile_token,
    }
    _emit_event(client, on_event, "sentinel_finalize_started")
    with suppress_web_session_debug_trace():
        finalize_status, finalize_data = client._json_request(
            "POST",
            f"{CHAT_URL.rstrip('/')}{SENTINEL_FINALIZE_PATH}",
            finalize_payload,
            _finalize_headers(client),
        )
    acquired_monotonic = time.monotonic()
    requirements_token, expires_monotonic = _validate_finalize_response(
        int(finalize_status),
        finalize_data,
        acquired_monotonic=acquired_monotonic,
    )
    bundle = FinalizedSentinelBundle(
        requirements_token=requirements_token,
        proof_token=proof_header,
        turnstile_token=turnstile_token,
        acquired_monotonic=acquired_monotonic,
        expires_monotonic=expires_monotonic,
    )
    response_keys = (
        sorted(str(key) for key in finalize_data)
        if isinstance(finalize_data, dict)
        else []
    )
    _write_structural_trace(
        client,
        "sentinel-finalize",
        {
            "method": "POST",
            "url": f"{CHAT_URL.rstrip('/')}{SENTINEL_FINALIZE_PATH}",
            "request_keys": ["prepare_token", "proofofwork", "turnstile"],
            "response_status": int(finalize_status),
            "response_keys": response_keys,
            "requirements_token_present": True,
            "proof_present": True,
            "turnstile_present": True,
            "raw_request_recorded": False,
            "raw_response_recorded": False,
            "challenge_values_recorded": False,
        },
    )
    _emit_event(
        client,
        on_event,
        "sentinel_bundle_finalized",
        status_code=int(finalize_status),
        requirements_token_present=True,
        proof_present=True,
        turnstile_present=True,
        expiry_present=True,
    )
    return bundle
