from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import threading
from typing import Any, Iterator

from .browser_authority_live_characterization import BrowserAuthorityCharacterizationProvider
from .client import ChatGPTWebClient
from .exceptions import RequestError
from .product_runtime import assemble_product_runtime

SCHEMA = 1
PROFILE_TO_PRODUCT_MODE: dict[str, str] = {
    "FAST": "INSTANT",
    "BALANCED": "MEDIUM",
    "DEEP": "HIGH",
}
PRODUCT_MODE_TO_SLIDER_INDEX: dict[str, int] = {
    "INSTANT": 0,
    "MEDIUM": 1,
    "HIGH": 2,
}
LIVE_SEQUENCE: tuple[str, ...] = ("FAST", "DEEP", "BALANCED")


def normalize_model_profile(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("model_profile must be a string")
    profile = value.strip().upper()
    if profile == "MAX":
        raise ValueError("MAX model profile is not mapped by the proven 3-state product slider")
    if profile not in PROFILE_TO_PRODUCT_MODE:
        supported = ", ".join((*PROFILE_TO_PRODUCT_MODE, "MAX(unmapped)"))
        raise ValueError(f"unsupported model_profile {value!r}; expected one of: {supported}")
    return profile


def product_mode_for_profile(value: str) -> str:
    return PROFILE_TO_PRODUCT_MODE[normalize_model_profile(value)]


class ProductModelProfileProvider(BrowserAuthorityCharacterizationProvider):
    """PR8.10 characterization provider using the normal production write path.

    The profile context only adds a strict ``requiredModelMode`` field to one
    already-authorized browser-owned turn. It does not add a fallback or retry.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._profile_context = threading.local()

    @contextmanager
    def require_profile(self, profile: str) -> Iterator[str]:
        normalized = normalize_model_profile(profile)
        if getattr(self._profile_context, "profile", None) is not None:
            raise RuntimeError("nested model-profile requirements are not supported")
        self._profile_context.profile = normalized
        try:
            yield normalized
        finally:
            if hasattr(self._profile_context, "profile"):
                del self._profile_context.profile

    def _rpc(
        self,
        payload: dict[str, Any],
        *,
        timeout: float,
        on_event=None,
    ) -> dict[str, Any]:
        outbound = payload
        profile = getattr(self._profile_context, "profile", None)
        if (
            isinstance(profile, str)
            and payload.get("type") == "turn"
            and isinstance(payload.get("text"), str)
            and bool(payload["text"].strip())
            and isinstance(payload.get("browserAuthorityLeaseId"), str)
            and bool(payload["browserAuthorityLeaseId"].strip())
        ):
            mode = PROFILE_TO_PRODUCT_MODE[profile]
            outbound = {
                **payload,
                "requiredModelMode": mode,
            }
            if mode == "INSTANT":
                outbound["requireNoReasoningRoute"] = True
        return super()._rpc(outbound, timeout=timeout, on_event=on_event)

    def model_profile_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        response = self._characterization_rpc(
            {"characterizeProductModelProfileSupport": True},
            timeout=timeout,
        )
        modes = response.get("supportedProductModes")
        indices = response.get("sliderIndices")
        return {
            "supported": response.get("modelProfileSelectionSupported") is True,
            "schema": response.get("modelProfileSelectionSchemaVersion"),
            "supported_product_modes": [item for item in modes if isinstance(item, str)]
            if isinstance(modes, list)
            else [],
            "slider_indices": dict(indices) if isinstance(indices, dict) else {},
            "strict_prewrite_verification": response.get("strictPrewriteVerification") is True,
            "max_profile_mapped": response.get("maxProfileMapped") is True,
        }

    def model_profile_selection_for_lease(
        self,
        lease_id: str,
        *,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise ValueError("lease_id is required")
        lease_id = lease_id.strip()
        response = self._characterization_rpc(
            {
                "characterizeProductModelProfileSelectionRecord": True,
                "expectedBrowserAuthorityLeaseId": lease_id,
            },
            timeout=timeout,
        )
        if response.get("modelProfileSelectionSupported") is not True:
            raise RequestError(
                "PR8_10_MODEL_PROFILE_SELECTION_NOT_SUPPORTED",
                request_stage="model_profile_characterization",
            )
        record = response.get("modelProfileSelection")
        if not isinstance(record, dict):
            raise RequestError(
                "PR8_10_MODEL_PROFILE_SELECTION_RECORD_MISSING",
                request_stage="model_profile_characterization",
            )
        if record.get("browserAuthorityLeaseId") != lease_id:
            raise RequestError(
                "PR8_10_MODEL_PROFILE_SELECTION_LEASE_MISMATCH",
                request_stage="model_profile_characterization",
            )
        return dict(record)


def _prompt(profile: str) -> str:
    return f"Reply with exactly: SDK_PR8_10_{profile}_OK"


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR8_10_MODEL_PROFILE_SUPPORT_NOT_PROVEN")
    if support.get("supported_product_modes") != ["INSTANT", "MEDIUM", "HIGH"]:
        raise RuntimeError("PR8_10_MODEL_PROFILE_MODE_SET_MISMATCH")
    if support.get("slider_indices") != PRODUCT_MODE_TO_SLIDER_INDEX:
        raise RuntimeError("PR8_10_MODEL_PROFILE_SLIDER_MAPPING_MISMATCH")
    if support.get("strict_prewrite_verification") is not True:
        raise RuntimeError("PR8_10_MODEL_PROFILE_STRICT_PREWRITE_NOT_PROVEN")
    if support.get("max_profile_mapped") is not False:
        raise RuntimeError("PR8_10_MAX_PROFILE_MUST_REMAIN_UNMAPPED")


def _validate_selection(profile: str, lease_id: str, record: dict[str, Any]) -> None:
    target = PROFILE_TO_PRODUCT_MODE[profile]
    if record.get("browserAuthorityLeaseId") != lease_id:
        raise RuntimeError(f"PR8_10_{profile}:LEASE_MISMATCH")
    if record.get("requestedModelMode") != target:
        raise RuntimeError(f"PR8_10_{profile}:REQUESTED_MODE_MISMATCH")
    if record.get("requestedSliderIndex") != PRODUCT_MODE_TO_SLIDER_INDEX[target]:
        raise RuntimeError(f"PR8_10_{profile}:SLIDER_INDEX_MISMATCH")
    if record.get("selectionComplete") is not True:
        raise RuntimeError(f"PR8_10_{profile}:SELECTION_NOT_COMPLETE")
    if record.get("selectedModeAfterProven") is not True:
        raise RuntimeError(f"PR8_10_{profile}:SELECTED_MODE_NOT_PROVEN")
    if record.get("selectedModeAfter") != target:
        raise RuntimeError(f"PR8_10_{profile}:SELECTED_MODE_MISMATCH")
    if record.get("conversationWriteBeforeSelection") is True:
        raise RuntimeError(f"PR8_10_{profile}:WRITE_BEFORE_SELECTION")


def run_live_gate(*, conversation: str, timeout: float = 150.0) -> dict[str, Any]:
    provider = ProductModelProfileProvider()
    client = ChatGPTWebClient(auto_login=False, auto_sentinel=False)
    runtime = assemble_product_runtime(client=client, provider=provider)

    support = provider.model_profile_support()
    _validate_support(support)

    report: dict[str, Any] = {
        "ok": False,
        "pr": "PR8.10.1",
        "schema": SCHEMA,
        "conversation": conversation,
        "product_write_budget": len(LIVE_SEQUENCE),
        "write_attempts": 0,
        "write_completions": 0,
        "automatic_write_retry": False,
        "semantic_profiles": dict(PROFILE_TO_PRODUCT_MODE),
        "max_profile": "UNMAPPED",
        "support": support,
        "turns": [],
    }

    for profile in LIVE_SEQUENCE:
        expected = f"SDK_PR8_10_{profile}_OK"
        report["write_attempts"] += 1
        with provider.require_profile(profile):
            execution = runtime.send_text_observed(
                _prompt(profile),
                conversation=conversation,
                timeout=timeout,
                conversation_mode="normal",
            )
        report["write_completions"] += 1
        actual = execution.response.text.strip()
        if actual != expected:
            raise RuntimeError(
                f"PR8_10_{profile}:UNEXPECTED_RESPONSE expected={expected!r} actual={actual!r}"
            )
        observation = execution.observation.to_dict()
        lease_id = observation.get("browser_authority_lease_id")
        if not isinstance(lease_id, str) or not lease_id:
            raise RuntimeError(f"PR8_10_{profile}:LEASE_ID_MISSING")
        selection = provider.model_profile_selection_for_lease(lease_id)
        _validate_selection(profile, lease_id, selection)
        report["turns"].append(
            {
                "profile": profile,
                "target_product_mode": PROFILE_TO_PRODUCT_MODE[profile],
                "response": actual,
                "browser_authority_lease_id": lease_id,
                "selection": selection,
            }
        )

    report["ok"] = True
    report["summary"] = {
        "profiles_proven": list(LIVE_SEQUENCE),
        "strict_prewrite_selection_supported": True,
        "all_three_slider_states_proven": True,
        "max_profile_mapped": False,
        "cross_conversation_scope_proven": False,
    }
    report["architecture_invalidation_check"] = {
        "current_product_runtime_boundary_invalidated": False,
        "existing_pr8_8_selector_reused": True,
        "silent_profile_fallback": False,
        "model_preservation_scope": "NOT_YET_PROVEN",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR8.10 three-profile strict product-mode live gate"
    )
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    parser.add_argument("--timeout", type=float, default=150.0)
    args = parser.parse_args()
    if not args.acknowledge_live_writes:
        parser.error("--acknowledge-live-writes is required; this gate performs exactly three product writes")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    report = run_live_gate(conversation=args.conversation.strip(), timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())