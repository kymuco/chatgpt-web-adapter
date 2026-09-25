from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

CLOSURE = EXT / "service_worker_rich_input_closure_repair_pr9_2.js"
SCHEMA10 = EXT / "service_worker_rich_input_schema10_repair_pr9_2.js"
SCHEMA11 = EXT / "service_worker_rich_input_schema11_repair_pr9_2.js"
SCHEMA12 = EXT / "service_worker_rich_input_schema12_repair_pr9_2.js"
SCHEMA15 = EXT / "service_worker_rich_input_schema15_repair_pr9_2.js"
SCHEMA24 = EXT / "service_worker_rich_input_schema24_repair_pr9_2.js"
OWNER = EXT / "service_worker_attachment_readiness.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_node(script: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def test_attachment_readiness_hooks_have_one_public_owner() -> None:
    closure = _source(CLOSURE)
    schema10 = _source(SCHEMA10)
    schema11 = _source(SCHEMA11)
    schema12 = _source(SCHEMA12)
    schema15 = _source(SCHEMA15)
    schema24 = _source(SCHEMA24)
    owner = _source(OWNER)

    assert "async function _pr92ClosureBaseReadPageOwnedAttachmentEvidence(" in closure
    assert "async function _pr92ClosureReadPageOwnedAttachmentEvidence(" not in closure

    assert "async function _pr92Schema11ReadPageOwnedAttachmentEvidence(" in schema11
    assert "_pr92Schema11PriorReadPageOwnedAttachmentEvidence" not in schema11
    assert "_pr92ClosureReadPageOwnedAttachmentEvidence =" not in schema11

    assert (
        "async function _pr92Schema10BaseRequireOfficialCleanComposerBeforeStaging("
        in schema10
    )
    assert (
        "async function _pr92Schema10RequireOfficialCleanComposerBeforeStaging("
        not in schema10
    )

    assert (
        "async function _pr92Schema12BaseObservePostStageAttachmentEvidence("
        in schema12
    )
    assert (
        "async function _pr92Schema12ObservePostStageAttachmentEvidence("
        not in schema12
    )

    assert (
        "async function _pr92Schema15RequireOfficialCleanComposerBeforeStaging("
        in schema15
    )
    assert "async function _pr92Schema15ObservePostStageAttachmentEvidence(" in schema15
    assert "_pr92Schema10RequireOfficialCleanComposerBeforeStaging =" not in schema15
    assert "_pr92Schema12ObservePostStageAttachmentEvidence =" not in schema15

    assert (
        "async function _pr92Schema24RequireOfficialCleanComposerBeforeStaging("
        in schema24
    )
    assert "_pr92Schema10RequireOfficialCleanComposerBeforeStaging =" not in schema24

    assert (
        owner.count("async function _pr92ClosureReadPageOwnedAttachmentEvidence(") == 1
    )
    assert (
        owner.count(
            "async function _pr92Schema10RequireOfficialCleanComposerBeforeStaging("
        )
        == 1
    )
    assert (
        owner.count("async function _pr92Schema12ObservePostStageAttachmentEvidence(")
        == 1
    )


def test_public_owner_selects_final_effective_generations() -> None:
    owner = _source(OWNER)

    assert "_pr92Schema11ReadPageOwnedAttachmentEvidence(" in owner
    assert "_pr92Schema24RequireOfficialCleanComposerBeforeStaging(" in owner
    assert "_pr92Schema15ObservePostStageAttachmentEvidence(" in owner


def test_write_domain_assembles_readiness_owner_after_schemas_before_staging() -> None:
    write = _source(WRITE)
    schemas = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'
    evidence = 'importScripts("service_worker_attachment_evidence.js");'
    owner = 'importScripts("service_worker_attachment_readiness.js");'
    cleanup = 'importScripts("service_worker_attachment_cleanup.js");'
    staging = 'importScripts("service_worker_attachment_staging.js");'

    for item in (schemas, evidence, owner, cleanup, staging):
        assert item in write
    assert (
        write.index(schemas)
        < write.index(evidence)
        < write.index(owner)
        < write.index(cleanup)
        < write.index(staging)
    )


def test_existing_consumers_resolve_public_readiness_hooks_at_call_time() -> None:
    closure = _source(CLOSURE)
    schema10 = _source(SCHEMA10)
    schema12 = _source(SCHEMA12)

    assert "await _pr92ClosureReadPageOwnedAttachmentEvidence(" in closure
    assert "await _pr92Schema10RequireOfficialCleanComposerBeforeStaging(" in schema10
    assert "return _pr92Schema12ObservePostStageAttachmentEvidence(" in schema12


def test_explicit_readiness_owner_delegates_once_without_argument_drift() -> None:
    owner = _source(OWNER)
    script = f"""
const calls = [];
async function _pr92Schema11ReadPageOwnedAttachmentEvidence(debuggee, expectedNames, context) {{
  calls.push(["read", debuggee, expectedNames, context]);
  return {{ ready: true }};
}}
async function _pr92Schema24RequireOfficialCleanComposerBeforeStaging(tabId, context) {{
  calls.push(["clean", tabId, context]);
  return "clean";
}}
async function _pr92Schema15ObservePostStageAttachmentEvidence(tabId, paths, context) {{
  calls.push(["post", tabId, paths, context]);
  return paths.length;
}}

{owner}

(async () => {{
  const debuggee = {{ tabId: 7 }};
  const expected = ["a.png"];
  const context = {{ deadlineAt: 42 }};
  const paths = ["/tmp/a.png", "/tmp/b.txt"];
  const read = await _pr92ClosureReadPageOwnedAttachmentEvidence(
    debuggee,
    expected,
    context
  );
  const clean = await _pr92Schema10RequireOfficialCleanComposerBeforeStaging(
    8,
    context
  );
  const post = await _pr92Schema12ObservePostStageAttachmentEvidence(
    9,
    paths,
    context
  );
  console.log(JSON.stringify({{
    calls,
    read,
    clean,
    post,
    sameDebuggee: calls[0][1] === debuggee,
    sameExpected: calls[0][2] === expected,
    sameReadContext: calls[0][3] === context,
    sameCleanContext: calls[1][2] === context,
    samePaths: calls[2][2] === paths,
    samePostContext: calls[2][3] === context
  }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)

    assert result["read"] == {"ready": True}
    assert result["clean"] == "clean"
    assert result["post"] == 2
    assert result["sameDebuggee"] is True
    assert result["sameExpected"] is True
    assert result["sameReadContext"] is True
    assert result["sameCleanContext"] is True
    assert result["samePaths"] is True
    assert result["samePostContext"] is True
    assert [call[0] for call in result["calls"]] == ["read", "clean", "post"]
