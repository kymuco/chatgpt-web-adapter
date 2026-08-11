from __future__ import annotations

import math
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


@dataclass(frozen=True, eq=False)
class SentinelChallengeContext:
    """Opaque current-prepare browser challenge context passed to a provider."""

    prepare_token: str = field(repr=False, compare=False)
    turnstile_dx: str = field(repr=False, compare=False)
    so_collector_dx: str = field(repr=False, compare=False)
    so_snapshot_dx: str = field(repr=False, compare=False)
    turnstile_required: bool
    proofofwork_required: bool
    so_required: bool


@dataclass(frozen=True, eq=False)
class SentinelChallengeEvidence:
    """One-shot provider evidence explicitly bound to the current prepare."""

    prepare_token: str = field(repr=False, compare=False)
    turnstile_dx: str = field(repr=False, compare=False)
    turnstile_token: str = field(repr=False, compare=False)
    so_collector_dx: str = field(repr=False, compare=False)
    so_snapshot_dx: str = field(repr=False, compare=False)
    so_completed: bool


SentinelChallengeProvider = Callable[
    [SentinelChallengeContext], SentinelChallengeEvidence
]


def set_sentinel_challenge_provider(
    client: Any,
    provider: SentinelChallengeProvider | None,
) -> None:
    """Install an in-memory current-prepare provider; never persists evidence."""

    if provider is not None and not callable(provider):
        raise TypeError("provider must be callable or None")
    client._sentinel_challenge_provider = provider


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


def _validate_required_flag(block: dict[str, Any], *, name: str, status: int) -> None:
    if not isinstance(block.get("required"), bool):
        raise RequestError(
            f"SENTINEL_PREPARE_CONTRACT_DRIFT: {name}.required is not boolean",
            status_code=int(status),
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )


def _validate_pow_descriptor(block: dict[str, Any], *, status: int) -> None:
    seed = block.get("seed")
    difficulty = block.get("difficulty")
    if not isinstance(seed, str) or not seed.strip():
        raise RequestError(
            "SENTINEL_PREPARE_CONTRACT_DRIFT: proofofwork.seed is not a non-empty string",
            status_code=int(status),
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )
    if (
        not isinstance(difficulty, str)
        or not difficulty
        or difficulty != difficulty.strip()
        or any(character not in "0123456789abcdefABCDEF" for character in difficulty)
    ):
        raise RequestError(
            "SENTINEL_PREPARE_CONTRACT_DRIFT: proofofwork.difficulty is not a non-empty hex string",
            status_code=int(status),
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )


def _required_descriptor(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequestError(
            f"SENTINEL_PREPARE_CONTRACT_DRIFT: required {name} descriptor is missing",
            endpoint=SENTINEL_PREPARE_PATH,
            request_stage="sentinel_prepare",
        )
    return value.strip()


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


def _challenge_context(
    response: dict[str, Any],
    *,
    prepare_token: str,
) -> SentinelChallengeContext:
    turnstile = response["turnstile"]
    proofofwork = response["proofofwork"]
    so = response["so"]
    return SentinelChallengeContext(
        prepare_token=prepare_token,
        turnstile_dx=_required_descriptor(
            turnstile.get("dx"),
            name="turnstile.dx",
        ),
        so_collector_dx=_required_descriptor(
            so.get("collector_dx"),
            name="so.collector_dx",
        ),
        so_snapshot_dx=_required_descriptor(
            so.get("snapshot_dx"),
            name="so.snapshot_dx",
        ),
        turnstile_required=turnstile["required"],
        proofofwork_required=proofofwork["required"],
        so_required=so["required"],
    )


def _obtain_current_prepare_evidence(
    client: Any,
    context: SentinelChallengeContext,
) -> SentinelChallengeEvidence:
    provider = getattr(client, "_sentinel_challenge_provider", None)
    if not callable(provider):
        raise RequestError(
            "SENTINEL_BROWSER_CHALLENGE_PROVIDER_REQUIRED: current two-phase "
            "Sentinel finalize requires a provider bound to this prepare challenge",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_challenge_provider",
        )
    try:
        evidence = provider(context)
    except RequestError:
        raise
    except Exception as error:
        raise RequestError(
            "SENTINEL_BROWSER_CHALLENGE_PROVIDER_FAILED: provider did not produce "
            "usable current-prepare evidence",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_challenge_provider",
        ) from error
    if not isinstance(evidence, SentinelChallengeEvidence):
        raise RequestError(
            "SENTINEL_BROWSER_CHALLENGE_PROVIDER_INVALID: provider returned an "
            "unsupported evidence object",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_challenge_provider",
        )
    if evidence.prepare_token != context.prepare_token:
        raise RequestError(
            "SENTINEL_CHALLENGE_BINDING_MISMATCH: provider evidence belongs to a "
            "different prepare transaction",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_challenge_binding",
        )
    if evidence.turnstile_dx != context.turnstile_dx:
        raise RequestError(
            "SENTINEL_CHALLENGE_BINDING_MISMATCH: provider Turnstile evidence "
            "belongs to a different challenge descriptor",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_challenge_binding",
        )
    if not isinstance(evidence.turnstile_token, str) or not evidence.turnstile_token.strip():
        raise RequestError(
            "SENTINEL_TURNSTILE_EVIDENCE_REQUIRED: current-prepare provider did "
            "not return Turnstile evidence",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_turnstile_gate",
        )
    if context.so_required:
        if evidence.so_completed is not True:
            raise RequestError(
                "SENTINEL_SO_CAPABILITY_REQUIRED: current prepare requires SO "
                "collector/snapshot completion before finalize",
                endpoint=SENTINEL_FINALIZE_PATH,
                request_stage="sentinel_so_gate",
            )
        if (
            evidence.so_collector_dx != context.so_collector_dx
            or evidence.so_snapshot_dx != context.so_snapshot_dx
        ):
            raise RequestError(
                "SENTINEL_CHALLENGE_BINDING_MISMATCH: provider SO evidence belongs "
                "to a different current-prepare descriptor",
                endpoint=SENTINEL_FINALIZE_PATH,
                request_stage="sentinel_challenge_binding",
            )
    return evidence


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
    _validate_required_flag(data["turnstile"], name="turnstile", status=status)
    _validate_required_flag(data["proofofwork"], name="proofofwork", status=status)
    _validate_required_flag(data["so"], name="so", status=status)
    _validate_pow_descriptor(data["proofofwork"], status=status)
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
    if not math.isfinite(ttl):
        raise RequestError(
            "SENTINEL_FINALIZE_CONTRACT_DRIFT: expire_after is not finite",
            status_code=int(status),
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_finalize",
        )
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
    """Acquire one two-phase bundle without challenge solving or credential replay."""

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
            "turnstile_required": turnstile["required"],
            "proofofwork_required": proofofwork["required"],
            "so_required": so["required"],
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
        turnstile_required=turnstile["required"],
        proofofwork_required=proofofwork["required"],
        so_required=so["required"],
    )
    if not all(
        (
            turnstile["required"] is True,
            proofofwork["required"] is True,
            so["required"] is True,
        )
    ):
        raise RequestError(
            "SENTINEL_FINALIZE_POLICY_UNOBSERVED: current finalize challenge "
            "combination has not been live-characterized",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_finalize_policy",
        )

    context = _challenge_context(response, prepare_token=prepare_token)
    evidence = _obtain_current_prepare_evidence(client, context)

    proof_header = client._build_proof_header({"proofofwork": proofofwork})
    if not isinstance(proof_header, str) or not proof_header.strip():
        raise RequestError(
            "Sentinel proof-of-work generation did not produce evidence",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_proof",
        )
    proof_header = proof_header.strip()
    turnstile_token = evidence.turnstile_token.strip()
    _emit_event(
        client,
        on_event,
        "sentinel_challenge_ready",
        proof_present=True,
        turnstile_present=True,
        so_completed=True,
        current_prepare_binding_verified=True,
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
            "so_completed": True,
            "current_prepare_binding_verified": True,
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