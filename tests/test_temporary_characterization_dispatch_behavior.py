from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = (
    ROOT
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
    / "service_worker_runtime_legacy_impl.js"
)


def _dispatcher_source() -> str:
    source = LEGACY.read_text(encoding="utf-8")
    start = source.index("function _cwaTemporaryCharacterizationMatches(message)")
    return source[start:]


def _run(message: dict) -> dict:
    prelude = f"""
const message = {json.dumps(message)};
const events = [];
let registration = null;

function registerNativeTurnDiagnosticHandler(name, matches, handle) {{
  registration = {{ name, matches, handle }};
}}
async function _pr87ProbeTemporaryRouteReopen() {{
  events.push("route");
  return {{ owner: "route" }};
}}
async function _pr87HandleManualTemporaryGroundTruth() {{
  events.push("manual");
  return {{ owner: "manual" }};
}}
async function _pr87HandleTemporaryHistoryCharacterization() {{
  events.push("history");
  return {{ owner: "history" }};
}}
async function _pr87HandleTemporaryTurnCharacterization() {{
  events.push("turn");
  return {{ owner: "turn" }};
}}
async function _pr87HandleTemporaryModeProbeWithAX() {{
  events.push("mode");
  return {{ owner: "mode" }};
}}
"""
    epilogue = """
(async () => {
  const matched = registration.matches(message);
  const result = matched ? await registration.handle(message) : null;
  console.log(JSON.stringify({
    registrationName: registration.name,
    matched,
    result,
    events
  }));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
"""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(prelude)
        handle.write("\n")
        handle.write(_dispatcher_source())
        handle.write("\n")
        handle.write(epilogue)
        path = handle.name
    try:
        result = subprocess.run(
            ["node", path],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return json.loads(result.stdout.strip().splitlines()[-1])
    finally:
        os.unlink(path)


def test_no_temporary_flag_does_not_claim_request() -> None:
    result = _run({"text": "ordinary"})

    assert result["registrationName"] == "temporary-characterization"
    assert result["matched"] is False
    assert result["result"] is None
    assert result["events"] == []


def test_each_temporary_characterization_routes_to_exact_owner() -> None:
    cases = (
        ({"probeTemporaryMode": True}, "mode"),
        ({"characterizeTemporaryTurn": True}, "turn"),
        ({"probeTemporaryHistoryPresence": True}, "history"),
        ({"characterizeManualTemporaryGroundTruth": True}, "manual"),
        ({"probeTemporaryRouteReopen": True}, "route"),
    )

    for message, owner in cases:
        result = _run(message)
        assert result["matched"] is True
        assert result["result"] == {"owner": owner}
        assert result["events"] == [owner]


def test_multi_flag_precedence_matches_historical_outer_wrapper_order() -> None:
    result = _run(
        {
            "probeTemporaryMode": True,
            "characterizeTemporaryTurn": True,
            "probeTemporaryHistoryPresence": True,
            "characterizeManualTemporaryGroundTruth": True,
            "probeTemporaryRouteReopen": True,
        }
    )

    assert result["matched"] is True
    assert result["result"] == {"owner": "route"}
    assert result["events"] == ["route"]

    result = _run(
        {
            "probeTemporaryMode": True,
            "characterizeTemporaryTurn": True,
            "probeTemporaryHistoryPresence": True,
            "characterizeManualTemporaryGroundTruth": True,
        }
    )
    assert result["result"] == {"owner": "manual"}
    assert result["events"] == ["manual"]

    result = _run(
        {
            "probeTemporaryMode": True,
            "characterizeTemporaryTurn": True,
            "probeTemporaryHistoryPresence": True,
        }
    )
    assert result["result"] == {"owner": "history"}
    assert result["events"] == ["history"]

    result = _run(
        {
            "probeTemporaryMode": True,
            "characterizeTemporaryTurn": True,
        }
    )
    assert result["result"] == {"owner": "turn"}
    assert result["events"] == ["turn"]
