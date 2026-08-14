from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import shutil
import subprocess
from typing import Any, Iterable

EVIDENCE_AS_OF = "2026-08-14"
FOUND = "SUPPORTED_NON_BROWSER_PRODUCT_WRITE_SURFACE_FOUND"
EXHAUSTED = "SUPPORTED_NON_BROWSER_PRODUCT_WRITE_SURFACE_EXHAUSTED"
BROWSER_NATIVE_BASELINE = "BROWSER_NATIVE_PAGE_OWNED_WRITE"


@dataclass(frozen=True)
class ProductExecutionSurface:
    surface_id: str
    name: str
    openai_supported: bool
    non_browser: bool
    external_programmatic_invocation: bool
    ordinary_chatgpt_chat_semantics: bool
    existing_conversation_continuity: bool
    chatgpt_memory_continuity: bool
    consumer_product_usage: bool
    direction: str
    disposition: str
    evidence_note: str

    def qualifies(self) -> bool:
        return bool(
            self.openai_supported
            and self.non_browser
            and self.external_programmatic_invocation
            and self.ordinary_chatgpt_chat_semantics
            and self.existing_conversation_continuity
            and self.chatgpt_memory_continuity
            and self.consumer_product_usage
            and self.direction == "external_client_to_chatgpt_chat"
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["qualifies"] = self.qualifies()
        return payload


SURFACES: tuple[ProductExecutionSurface, ...] = (
    ProductExecutionSurface(
        surface_id="chatgpt_desktop",
        name="ChatGPT desktop app (Chat)",
        openai_supported=True,
        non_browser=True,
        external_programmatic_invocation=False,
        ordinary_chatgpt_chat_semantics=True,
        existing_conversation_continuity=True,
        chatgpt_memory_continuity=True,
        consumer_product_usage=True,
        direction="human_client_to_chatgpt_chat",
        disposition="NATIVE_CLIENT_WITHOUT_DOCUMENTED_EXTERNAL_TURN_CONTRACT",
        evidence_note=(
            "Official desktop app exposes Chat/Work/Codex and syncs Chat conversations, "
            "but no supported external Chat turn IPC/SDK/CLI contract was identified."
        ),
    ),
    ProductExecutionSurface(
        surface_id="openai_api",
        name="OpenAI API",
        openai_supported=True,
        non_browser=True,
        external_programmatic_invocation=True,
        ordinary_chatgpt_chat_semantics=False,
        existing_conversation_continuity=False,
        chatgpt_memory_continuity=False,
        consumer_product_usage=False,
        direction="external_client_to_openai_api",
        disposition="SEPARATE_PRODUCT",
        evidence_note="API is a supported programmatic model surface with separate billing/product state.",
    ),
    ProductExecutionSurface(
        surface_id="sign_in_with_chatgpt",
        name="Sign in with ChatGPT",
        openai_supported=True,
        non_browser=True,
        external_programmatic_invocation=True,
        ordinary_chatgpt_chat_semantics=False,
        existing_conversation_continuity=False,
        chatgpt_memory_continuity=False,
        consumer_product_usage=False,
        direction="chatgpt_identity_to_external_app",
        disposition="IDENTITY_ONLY",
        evidence_note=(
            "Sign-in shares approved identity information; it does not independently grant "
            "conversation, memory, file, token, or billing access."
        ),
    ),
    ProductExecutionSurface(
        surface_id="apps_sdk_mcp",
        name="Apps SDK / MCP",
        openai_supported=True,
        non_browser=True,
        external_programmatic_invocation=True,
        ordinary_chatgpt_chat_semantics=False,
        existing_conversation_continuity=False,
        chatgpt_memory_continuity=False,
        consumer_product_usage=True,
        direction="chatgpt_to_external_tool",
        disposition="REVERSE_DIRECTION",
        evidence_note="The supported integration direction is ChatGPT invoking external tools/data.",
    ),
    ProductExecutionSurface(
        surface_id="codex_cli_sdk",
        name="Codex CLI / SDK",
        openai_supported=True,
        non_browser=True,
        external_programmatic_invocation=True,
        ordinary_chatgpt_chat_semantics=False,
        existing_conversation_continuity=False,
        chatgpt_memory_continuity=False,
        consumer_product_usage=True,
        direction="external_client_to_codex",
        disposition="AGENTIC_SURFACE_NOT_CHATGPT_CHAT",
        evidence_note=(
            "Codex is programmable and can be included with ChatGPT plans, but its workflows/history "
            "are separate from ordinary ChatGPT Chat."
        ),
    ),
    ProductExecutionSurface(
        surface_id="compliance_platform",
        name="OpenAI Compliance Platform",
        openai_supported=True,
        non_browser=True,
        external_programmatic_invocation=True,
        ordinary_chatgpt_chat_semantics=False,
        existing_conversation_continuity=False,
        chatgpt_memory_continuity=False,
        consumer_product_usage=False,
        direction="external_compliance_client_to_workspace_logs",
        disposition="AUDIT_AND_COMPLIANCE_DATA_ONLY",
        evidence_note="Compliance APIs expose workspace audit/log/state data, not ordinary Chat turn execution.",
    ),
)


def supported_surface_matrix(
    surfaces: Iterable[ProductExecutionSurface] = SURFACES,
) -> list[dict[str, Any]]:
    return [surface.to_dict() for surface in surfaces]


def closure_verdict(
    surfaces: Iterable[ProductExecutionSurface] = SURFACES,
) -> tuple[str, list[str]]:
    qualifying = [surface.surface_id for surface in surfaces if surface.qualifies()]
    return (FOUND if qualifying else EXHAUSTED, qualifying)


def _powershell_chatgpt_packages() -> tuple[bool, list[dict[str, str]], str | None]:
    if os.name != "nt":
        return False, [], "NOT_WINDOWS"
    powershell = shutil.which("powershell") or shutil.which("powershell.exe")
    if powershell is None:
        return False, [], "POWERSHELL_NOT_FOUND"
    command = (
        "Get-AppxPackage *ChatGPT* | "
        "Select-Object Name,PackageFullName | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return False, [], type(error).__name__.upper()
    if completed.returncode != 0:
        return False, [], "POWERSHELL_QUERY_FAILED"
    text = completed.stdout.strip()
    if not text:
        return True, [], None
    try:
        decoded = json.loads(text)
    except ValueError:
        return False, [], "POWERSHELL_JSON_INVALID"
    items = decoded if isinstance(decoded, list) else [decoded]
    packages: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("Name")
        full = item.get("PackageFullName")
        packages.append(
            {
                "name": name if isinstance(name, str) else "",
                "package_full_name": full if isinstance(full, str) else "",
            }
        )
    return True, packages, None


def native_client_inventory() -> dict[str, Any]:
    query_ok, packages, error_kind = _powershell_chatgpt_packages()
    codex_path = shutil.which("codex") or shutil.which("codex.exe")
    return {
        "platform": os.name,
        "chatgpt_package_query_attempted": os.name == "nt",
        "chatgpt_package_query_ok": query_ok,
        "chatgpt_packages": packages,
        "codex_cli_present": codex_path is not None,
        "codex_cli_executable_name": os.path.basename(codex_path) if codex_path else None,
        "error_kind": error_kind,
        "governance": {
            "launches_native_client": False,
            "native_ui_automation": False,
            "private_storage_read": False,
            "undocumented_ipc_probe": False,
            "credential_extraction": False,
        },
    }


def product_execution_closure_report(*, include_native_inventory: bool = False) -> dict[str, Any]:
    verdict, qualifying = closure_verdict()
    report: dict[str, Any] = {
        "pr": "PR8.2.3",
        "evidence_as_of": EVIDENCE_AS_OF,
        "verdict": verdict,
        "supported_non_browser_product_write_available": bool(qualifying),
        "qualifying_surface_ids": qualifying,
        "acceptance_contract": {
            "openai_supported": True,
            "non_browser": True,
            "external_programmatic_invocation": True,
            "ordinary_chatgpt_chat_semantics": True,
            "existing_conversation_continuity": True,
            "chatgpt_memory_continuity": True,
            "consumer_product_usage": True,
            "direction": "external_client_to_chatgpt_chat",
        },
        "surfaces": supported_surface_matrix(),
        "closure": {
            "browserless_turn_provider_eligible": bool(qualifying),
            "minimum_proven_supported_product_write_runtime": (
                None if qualifying else BROWSER_NATIVE_BASELINE
            ),
            "reopen_condition": (
                "A documented OpenAI-supported surface must satisfy every acceptance-contract field."
            ),
        },
        "governance": {
            "direct_private_product_write_probe": False,
            "challenge_solver_expansion": False,
            "browser_protection_emulation": False,
            "credential_extraction": False,
            "native_ui_automation": False,
            "undocumented_native_ipc_probe": False,
        },
    }
    if include_native_inventory:
        report["native_inventory"] = native_client_inventory()
    return report
