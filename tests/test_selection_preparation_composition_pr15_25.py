from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
OWNER = "service_worker_selection_preparation.js"


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


def test_selection_preparation_is_single_composer_owner() -> None:
    owner = _source(OWNER)
    assert owner.count("locateAndFocusComposer =") == 1

    retired_aliases = {
        "service_worker_instant_mode_pr8_8.js": "_pr88InstantPriorLocateAndFocusComposer",
        "service_worker_instant_selection_repair_pr8_8.js": (
            "_pr88SelectionPriorLocateAndFocusComposer"
        ),
        "service_worker_model_profile_selection_pr8_10.js": (
            "_pr810ModelProfilePriorLocateAndFocusComposer"
        ),
    }
    for name, alias in retired_aliases.items():
        source = _source(name)
        assert "locateAndFocusComposer =" not in source, name
        assert alias not in source, name


def test_selection_preparation_preserves_historical_outer_to_inner_order() -> None:
    owner = _source(OWNER)
    markers = (
        "await _pr810PrepareComposer(debuggee);",
        "await _pr88SelectionPrepareComposer(debuggee);",
        "await _pr88InstantObserveComposerBeforeWrite(debuggee);",
        "return _cwaSelectionPreparationPriorLocateAndFocusComposer(debuggee);",
    )
    positions = [owner.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_selection_preparation_runtime_handoff_matches_historical_chain() -> None:
    owner = _source(OWNER)
    script = f"""
const events = [];

let locateAndFocusComposer = async () => {{
  events.push("base");
  return {{ focused: true }};
}};

async function _pr810PrepareComposer() {{
  events.push("model");
}}

async function _pr88SelectionPrepareComposer() {{
  events.push("selection");
}}

async function _pr88InstantObserveComposerBeforeWrite() {{
  events.push("instant");
}}

{owner}

(async () => {{
  const result = await locateAndFocusComposer({{ tabId: 1 }});
  console.log(JSON.stringify({{ events, result }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)
    assert result["events"] == ["model", "selection", "instant", "base"]
    assert result["result"] == {"focused": True}
