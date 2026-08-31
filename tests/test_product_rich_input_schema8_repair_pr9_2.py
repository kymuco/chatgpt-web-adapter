from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
SCHEMA8 = EXT / "service_worker_rich_input_schema8_repair_pr9_2.js"
SCHEMA7_LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"


def test_schema_8_overlay_is_loaded_immediately_after_schema_7_core():
    text = SCHEMA7_LOADER.read_text(encoding="utf-8")
    core = 'importScripts("service_worker_rich_input_schema7_core_pr9_2.js");'
    schema8 = 'importScripts("service_worker_rich_input_schema8_repair_pr9_2.js");'

    assert core in text
    assert schema8 in text
    assert text.index(core) < text.index(schema8)


def test_schema_8_requires_clean_composer_and_exact_attachment_set():
    text = SCHEMA8.read_text(encoding="utf-8")

    assert "const PR92_SCHEMA8_REPAIR_SCHEMA = 8;" in text
    assert "_pr92Schema8RequireAttachmentCleanComposerBeforeStaging" in text
    assert 'PR9_2_PREEXISTING_COMPOSER_ATTACHMENT_PRESENT' in text
    assert "matchesExpectedExactly" in text
    assert "pool.length === 0" in text
    assert "exactAttachmentSet" in text
    assert "preStageComposerAttachmentClean: true" in text
    assert "exactComposerAttachmentSetRequired: true" in text

    stage = text[
        text.index("_pr92StageOfficialPageAttachments = async function _pr92Schema8StageFromCleanComposer") :
        text.index("function _pr92Schema8FenceIdentityMatches")
    ]
    assert stage.index("_pr92Schema8RequireAttachmentCleanComposerBeforeStaging") < stage.index(
        "_pr92Schema8PriorStageOfficialPageAttachments"
    )


def test_schema_8_revalidates_destructive_authority_at_close_boundary():
    text = SCHEMA8.read_text(encoding="utf-8")
    cleanup = text[
        text.index("_pr92ClearOfficialPageAttachments = async function _pr92Schema8ClearFencedRuntimeTab") :
        text.index("executeNativeTurn = async function _executeNativeTurnWithPr92Schema8Repair")
    ]

    assert "chrome.tabs.onUpdated.addListener(onUpdated)" in cleanup
    assert "chrome.tabs.onRemoved.addListener(onRemoved)" in cleanup
    assert "chrome.storage.onChanged.addListener(onStorageChanged)" in cleanup
    assert '"CLEANUP_RUNTIME_IDENTITY_FINAL_ID"' in cleanup
    assert '"CLEANUP_RUNTIME_TAB_FINAL_LOOKUP"' in cleanup
    assert "finalCandidate.url !== candidate.url" in cleanup
    assert "destructiveCleanupAuthorityRevalidatedAtClose: true" in text
    assert "destructiveCleanupOwnershipChangeFailsClosed: true" in text

    final_lookup = cleanup.index('"CLEANUP_RUNTIME_TAB_FINAL_LOOKUP"')
    final_guard = cleanup.index("if (\n      ownershipInvalidated", final_lookup)
    close_dispatched = cleanup.index("closeDispatched = true;", final_guard)
    close_call = cleanup.index("chrome.tabs.remove(tabId)", close_dispatched)
    assert final_lookup < final_guard < close_dispatched < close_call

    between_guard_and_close = cleanup[close_dispatched:close_call]
    assert "await " not in between_guard_and_close


def test_all_packaged_extension_javascript_parses_with_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is unavailable")

    failures: list[str] = []
    for path in sorted(EXT.glob("*.js")):
        proc = subprocess.run(
            [node, "--check", str(path)],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            failures.append(f"{path.name}: {proc.stderr.strip()}")

    assert failures == []
