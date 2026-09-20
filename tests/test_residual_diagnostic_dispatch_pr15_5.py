from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

DETACHED = (
    "service_worker_reasoning_effort_slider_geometry_pr8_8.js",
    "service_worker_rich_input_schema23_diagnostic_pr9_2.js",
    "service_worker_rich_input_schema26_staging_diagnostic_pr9_2.js",
    "service_worker_rich_input_schema27_staging_diagnostic_pr9_2.js",
    "service_worker_rich_input_schema28_diagnostic_repair_pr9_2.js",
)

GOVERNANCE = EXT / "service_worker_reasoning_effort_slider_governance_pr8_8.js"
RICH_OWNER = EXT / "service_worker_rich_input_schema28_diagnostic_repair_pr9_2.js"


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


def test_residual_diagnostic_modules_do_not_own_ordinary_turn_dispatch():
    for name in DETACHED:
        source = _source(name)
        assert "executeNativeTurn = async function" not in source, name
        assert "PriorExecuteNativeTurn" not in source, name


def test_reasoning_effort_geometry_joins_existing_explicit_owner():
    governance = GOVERNANCE.read_text(encoding="utf-8")
    geometry = _source("service_worker_reasoning_effort_slider_geometry_pr8_8.js")

    assert '"reasoning-effort-characterization"' in governance
    assert "registerNativeTurnDiagnosticHandler(" in governance
    assert "characterizeReasoningEffortGeometrySupport" in governance
    assert "characterizeReasoningEffortGeometry" in governance
    assert "_pr88HandleReasoningEffortGeometryDiagnostic(message)" in governance
    assert "async function _pr88HandleReasoningEffortGeometryDiagnostic" in geometry

    handler = governance[
        governance.index("async function _pr88HandleReasoningEffortDiagnostic") :
    ]
    geometry_branch = handler.index("characterizeReasoningEffortGeometrySupport")
    slider_branch = handler.index("characterizeReasoningEffortSliderSupport")
    assert geometry_branch < slider_branch


def test_rich_input_diagnostics_have_one_explicit_owner_and_frozen_precedence():
    owner = RICH_OWNER.read_text(encoding="utf-8")

    assert 'registerNativeTurnDiagnosticHandler(\n  "rich-input-diagnostics"' in owner
    handler = owner[owner.index("async function _cwaHandleRichInputDiagnostic") :]

    schema28 = handler.index(
        "message?.diagnosePr92CommittedIdentityStateSchema28 === true"
    )
    schema27 = handler.index(
        "message?.diagnosePr92StagedAttachmentEvidenceSchema27 === true"
    )
    schema26 = handler.index("message?.diagnosePr92StagedAttachmentEvidence === true")
    composer = handler.index("message?.diagnosePr92ComposerEvidence === true")
    assert schema28 < schema27 < schema26 < composer

    combined_sources = "\n".join(_source(name) for name in DETACHED)
    assert combined_sources.count('"rich-input-diagnostics"') == 1


def test_rich_input_dispatch_preserves_historical_composition_behavior():
    owner = RICH_OWNER.read_text(encoding="utf-8")
    block = owner[owner.index("function _cwaRichInputDiagnosticMatches") :]

    script = f"""
const events = [];
let registration = null;

function registerNativeTurnDiagnosticHandler(name, matches, handle) {{
  registration = {{ name, matches, handle }};
}}

function _pr92Schema28PrepareRichWriteDiagnostics() {{ events.push("prep28"); }}
function _pr92Schema29PrepareRichWriteDiagnostics() {{ events.push("prep29"); }}

async function _pr92Schema28CommittedIdentityDiagnosticRepaired() {{
  events.push("run28");
  return {{ layers: ["run28"] }};
}}
async function _pr92RunSchema27StagingDiagnostic() {{
  events.push("run27");
  return {{ layers: ["run27"] }};
}}
async function _pr92RunSchema26StagingDiagnostic() {{
  events.push("run26");
  return {{ layers: ["run26"] }};
}}
async function _pr92RunSchema23ComposerDiagnostic() {{
  events.push("run23");
  return {{ layers: ["run23"] }};
}}

function add(result, layer) {{
  return {{ ...result, layers: [...result.layers, layer] }};
}}
function _pr92Schema25AugmentComposerDiagnostic(result) {{ return add(result, "c25"); }}
function _pr92Schema26AugmentComposerDiagnostic(result) {{ return add(result, "c26"); }}
function _pr92Schema27AugmentComposerDiagnostic(result) {{ return add(result, "c27"); }}
function _pr92Schema27AugmentSupportResult(result) {{ return add(result, "s27"); }}
function _pr92Schema28AugmentSupportResult(result) {{ return add(result, "s28"); }}
function _pr92Schema29AugmentSupportResult(result) {{ return add(result, "s29"); }}

{block}

(async () => {{
  const ordinary = registration.matches({{ text: "ordinary" }});
  const combined = await registration.handle({{
    diagnosePr92CommittedIdentityStateSchema28: true,
    diagnosePr92StagedAttachmentEvidenceSchema27: true,
    diagnosePr92StagedAttachmentEvidence: true,
    diagnosePr92ComposerEvidence: true
  }});
  const composer = await registration.handle({{ diagnosePr92ComposerEvidence: true }});
  const stage26 = await registration.handle({{
    diagnosePr92StagedAttachmentEvidence: true,
    characterizeRichInputSupport: true
  }});
  const stage27 = await registration.handle({{
    diagnosePr92StagedAttachmentEvidenceSchema27: true,
    characterizeRichInputSupport: true
  }});
  const committed28 = await registration.handle({{
    diagnosePr92CommittedIdentityStateSchema28: true,
    characterizeRichInputSupport: true
  }});

  console.log(JSON.stringify({{
    name: registration.name,
    ordinary,
    combined: combined.layers,
    composer: composer.layers,
    stage26: stage26.layers,
    stage27: stage27.layers,
    committed28: committed28.layers
  }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""

    result = _run_node(script)
    assert result["name"] == "rich-input-diagnostics"
    assert result["ordinary"] is False
    assert result["combined"] == ["run28"]
    assert result["composer"] == ["run23", "c25", "c26", "c27"]
    assert result["stage26"] == ["run26", "s27", "s28", "s29"]
    assert result["stage27"] == ["run27", "s28", "s29"]
    assert result["committed28"] == ["run28", "s29"]
