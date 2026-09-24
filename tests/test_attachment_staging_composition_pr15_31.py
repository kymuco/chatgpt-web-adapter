from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
WRITE = EXT / "service_worker_runtime_write.js"
OWNER = EXT / "service_worker_attachment_staging.js"

LAYERS = {
    "service_worker_rich_input_pr9_2.js": "_pr92BaseStageOfficialPageAttachments",
    "service_worker_rich_input_closure_repair_pr9_2.js": (
        "_pr92StageWithPageOwnedEvidence"
    ),
    "service_worker_rich_input_schema8_repair_pr9_2.js": (
        "_pr92Schema8StageFromCleanComposer"
    ),
    "service_worker_rich_input_schema10_repair_pr9_2.js": (
        "_pr92Schema10StageFromOfficialCleanComposer"
    ),
    "service_worker_rich_input_schema12_repair_pr9_2.js": (
        "_pr92Schema12StageWithBoundedPostStageEvidence"
    ),
    "service_worker_rich_input_schema13_repair_pr9_2.js": (
        "_pr92Schema13FullyBoundedStage"
    ),
}


def _source(name: str) -> str:
    return (EXT / name).read_text(encoding="utf-8")


def _run_node(script: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def test_attachment_staging_has_one_public_owner() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    assert owner.count("async function _pr92StageOfficialPageAttachments(") == 1
    assert "_pr92StageOfficialPageAttachments =" not in owner

    for name, helper in LAYERS.items():
        source = _source(name)
        assert helper in source, (name, helper)
        assert "_pr92StageOfficialPageAttachments =" not in source, name
        assert "PriorStageOfficialPageAttachments" not in source, name

    assert "async function _pr92StageOfficialPageAttachments(" not in _source(
        "service_worker_rich_input_pr9_2.js"
    )


def test_write_domain_assembles_staging_owner_after_schema_generations() -> None:
    write = WRITE.read_text(encoding="utf-8")
    schemas = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    owner = 'importScripts("service_worker_attachment_staging.js");'
    lifecycle = 'importScripts("service_worker_rich_input_lifecycle.js");'

    assert schemas in write
    assert owner in write
    assert lifecycle in write
    assert write.index(schemas) < write.index(owner) < write.index(lifecycle)


def test_public_staging_owner_graduates_schema13_final_generation() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    assert "_pr92Schema13FullyBoundedStage(tabId, attachmentPaths, context)" in owner


def test_explicit_staging_owner_delegates_once_without_argument_drift() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    script = f"""
const calls = [];
async function _pr92Schema13FullyBoundedStage(tabId, attachmentPaths, context) {{
  calls.push({{ tabId, attachmentPaths, context }});
  return 2;
}}

{owner}

(async () => {{
  const attachments = ["a.png", "b.txt"];
  const context = {{ deadlineAt: 1234 }};
  const result = await _pr92StageOfficialPageAttachments(17, attachments, context);
  console.log(JSON.stringify({{
    calls,
    result,
    sameAttachments: calls[0].attachmentPaths === attachments,
    sameContext: calls[0].context === context
  }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)
    assert result["result"] == 2
    assert len(result["calls"]) == 1
    assert result["calls"][0]["tabId"] == 17
    assert result["calls"][0]["attachmentPaths"] == ["a.png", "b.txt"]
    assert result["sameAttachments"] is True
    assert result["sameContext"] is True


def test_historical_staging_generations_have_explicit_dependencies() -> None:
    closure = _source("service_worker_rich_input_closure_repair_pr9_2.js")
    schema8 = _source("service_worker_rich_input_schema8_repair_pr9_2.js")
    schema10 = _source("service_worker_rich_input_schema10_repair_pr9_2.js")
    schema12 = _source("service_worker_rich_input_schema12_repair_pr9_2.js")
    schema13 = _source("service_worker_rich_input_schema13_repair_pr9_2.js")

    assert "_pr92BaseStageOfficialPageAttachments(" in closure
    assert "_pr92StageWithPageOwnedEvidence(" in schema8
    assert "_pr92StageWithPageOwnedEvidence(" in schema10
    assert "_pr92BaseStageOfficialPageAttachments(" in schema12

    stage13 = schema13[
        schema13.index(
            "async function _pr92Schema13FullyBoundedStage"
        ) : schema13.index("function _pr92Schema13AugmentSupportResult")
    ]
    clean = "_pr92Schema10RequireOfficialCleanComposerBeforeStaging("
    select = "_pr92Schema13StageFileSelection("
    observe = "_pr92Schema12ObservePostStageAttachmentEvidence("
    assert clean in stage13
    assert select in stage13
    assert observe in stage13
    assert stage13.index(clean) < stage13.index(select) < stage13.index(observe)
