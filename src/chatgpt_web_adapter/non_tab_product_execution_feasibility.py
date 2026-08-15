from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

SUPPORTED_NON_TAB_PRODUCT_EXECUTION_VERDICT = (
    "SUPPORTED_NON_TAB_ORDINARY_CHATGPT_PRODUCT_EXECUTION_NOT_FOUND"
)

SOURCE_MATRIX: tuple[dict[str, str], ...] = (
    {
        "id": "C0",
        "topic": "offscreen_document",
        "source": "https://developer.chrome.com/docs/extensions/reference/api/offscreen",
        "fact": (
            "offscreen documents are hidden DOM contexts, but their top-level URL "
            "must be a static HTML file bundled with the extension and chrome.runtime "
            "is the only extension API available inside the document"
        ),
    },
    {
        "id": "C1",
        "topic": "mv3_service_worker",
        "source": "https://developer.chrome.com/docs/extensions/develop/migrate/to-service-workers",
        "fact": "Manifest V3 service workers do not expose DOM or window APIs",
    },
    {
        "id": "C2",
        "topic": "debugger_targets",
        "source": "https://developer.chrome.com/docs/extensions/reference/api/debugger",
        "fact": (
            "chrome.debugger can attach by tabId, extensionId, or targetId to an "
            "existing debug target; target attachment does not itself define a hidden "
            "ordinary-site page creation surface"
        ),
    },
    {
        "id": "C3",
        "topic": "extension_embedding_storage",
        "source": "https://developer.chrome.com/docs/extensions/develop/concepts/storage-and-cookies",
        "fact": (
            "a third-party site embedded by a chrome-extension page executes in an "
            "embedded storage/cookie context rather than the same top-level browsing "
            "context as direct navigation"
        ),
    },
)

SURFACE_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "gate": "N0",
        "surface_id": "current_reusable_inactive_tab",
        "supported_chrome_surface": True,
        "non_tab": False,
        "ordinary_top_level_chatgpt": True,
        "semantics_preserved": True,
        "verdict": "PROVEN_BASELINE",
        "boundary": (
            "PR8.2.4a.3 proves one reusable inactive chatgpt.com tab with no observed "
            "foreground activation"
        ),
    },
    {
        "gate": "N1",
        "surface_id": "mv3_service_worker",
        "supported_chrome_surface": True,
        "non_tab": True,
        "ordinary_top_level_chatgpt": False,
        "semantics_preserved": False,
        "verdict": "REJECTED_NO_DOM_WINDOW",
        "boundary": "cannot host the ordinary ChatGPT page runtime",
    },
    {
        "gate": "N2",
        "surface_id": "offscreen_document_top_level",
        "supported_chrome_surface": True,
        "non_tab": True,
        "ordinary_top_level_chatgpt": False,
        "semantics_preserved": False,
        "verdict": "REJECTED_EXTENSION_URL_ONLY",
        "boundary": (
            "chrome.offscreen top-level URL must be extension-packaged HTML, not "
            "https://chatgpt.com"
        ),
    },
    {
        "gate": "N3",
        "surface_id": "offscreen_cross_origin_iframe",
        "supported_chrome_surface": True,
        "non_tab": True,
        "ordinary_top_level_chatgpt": False,
        "semantics_preserved": False,
        "verdict": "DOES_NOT_MEET_TOP_LEVEL_PRODUCT_CONTRACT",
        "boundary": (
            "cross-origin iframe embedding is an embedded extension-origin context; "
            "it is not ordinary top-level ChatGPT navigation and storage/cookie "
            "semantics can differ"
        ),
    },
    {
        "gate": "N4",
        "surface_id": "offscreen_extension_api_control",
        "supported_chrome_surface": True,
        "non_tab": True,
        "ordinary_top_level_chatgpt": False,
        "semantics_preserved": False,
        "verdict": "RUNTIME_API_ONLY",
        "boundary": (
            "offscreen documents only expose chrome.runtime from the extension API; "
            "tab/debugger orchestration remains outside that document"
        ),
    },
    {
        "gate": "N5",
        "surface_id": "debugger_target_id",
        "supported_chrome_surface": True,
        "non_tab": True,
        "ordinary_top_level_chatgpt": False,
        "semantics_preserved": False,
        "verdict": "ATTACHMENT_PRIMITIVE_NOT_EXECUTION_SURFACE",
        "boundary": (
            "targetId can identify an existing target but does not establish a "
            "supported hidden top-level chatgpt.com target creation contract"
        ),
    },
    {
        "gate": "N6",
        "surface_id": "popup_side_panel_or_minimized_window",
        "supported_chrome_surface": True,
        "non_tab": False,
        "ordinary_top_level_chatgpt": False,
        "semantics_preserved": False,
        "verdict": "USER_VISIBLE_OR_NON_TOP_LEVEL_SURFACE",
        "boundary": "does not satisfy the hidden non-tab ordinary-product requirement",
    },
    {
        "gate": "N7",
        "surface_id": "qualifying_supported_non_tab_product_runtime",
        "supported_chrome_surface": False,
        "non_tab": True,
        "ordinary_top_level_chatgpt": True,
        "semantics_preserved": True,
        "verdict": SUPPORTED_NON_TAB_PRODUCT_EXECUTION_VERDICT,
        "boundary": "no qualifying supported Chrome surface identified",
    },
    {
        "gate": "N8",
        "surface_id": "minimum_proven_write_substrate",
        "supported_chrome_surface": True,
        "non_tab": False,
        "ordinary_top_level_chatgpt": True,
        "semantics_preserved": True,
        "verdict": "ONE_REUSABLE_INACTIVE_TAB",
        "boundary": "retain PR8.2.4a.3 as the minimum proven ordinary-product write substrate",
    },
)


@dataclass(frozen=True)
class CurrentWriteSurfaceProbeResult:
    attempted: bool
    bridge_available: bool
    extension_connected: bool
    runtime_tab_id: int | None
    runtime_tab_present: bool
    observed_surface: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def source_matrix() -> list[dict[str, str]]:
    return [dict(item) for item in SOURCE_MATRIX]


def surface_matrix() -> list[dict[str, Any]]:
    return [dict(item) for item in SURFACE_MATRIX]


def qualifying_surface_ids() -> list[str]:
    return [
        str(item["surface_id"])
        for item in SURFACE_MATRIX
        if item["non_tab"] is True
        and item["ordinary_top_level_chatgpt"] is True
        and item["semantics_preserved"] is True
        and item["supported_chrome_surface"] is True
    ]


def base_non_tab_feasibility_report() -> dict[str, Any]:
    qualifying = qualifying_surface_ids()
    return {
        "verdict": SUPPORTED_NON_TAB_PRODUCT_EXECUTION_VERDICT,
        "supported_non_tab_ordinary_chatgpt_product_execution_available": bool(qualifying),
        "qualifying_surface_ids": qualifying,
        "surfaces": surface_matrix(),
        "sources": source_matrix(),
        "governance": {
            "supported_browser_surfaces_only": True,
            "ordinary_top_level_chatgpt_semantics_required": True,
            "embedded_iframe_not_equated_with_top_level_product_runtime": True,
            "direct_private_product_write": False,
            "credential_extraction_or_replay": False,
            "browser_protection_emulation": False,
            "challenge_solver_expansion": False,
            "non_tab_write_probe_performed": False,
            "current_reusable_inactive_tab_baseline_preserved": True,
            "verdict_reopenable_if_new_supported_surface_appears": True,
        },
    }


def run_current_write_surface_probe(provider: Any) -> CurrentWriteSurfaceProbeResult:
    status = provider.status()
    runtime_tab_id = getattr(status, "runtime_tab_id", None)
    if isinstance(runtime_tab_id, bool) or not isinstance(runtime_tab_id, int):
        runtime_tab_id = None
    bridge_available = bool(getattr(status, "available", False))
    extension_connected = bool(getattr(status, "extension_connected", False))
    runtime_tab_present = runtime_tab_id is not None
    observed_surface = (
        "REUSABLE_TAB_PRESENT"
        if runtime_tab_present
        else "TAB_ON_DEMAND_BASELINE"
        if bridge_available and extension_connected
        else "NO_CONNECTED_BROWSER_WRITE_SURFACE"
    )
    return CurrentWriteSurfaceProbeResult(
        attempted=True,
        bridge_available=bridge_available,
        extension_connected=extension_connected,
        runtime_tab_id=runtime_tab_id,
        runtime_tab_present=runtime_tab_present,
        observed_surface=observed_surface,
    )
