from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"

WORKERS = (
    "service_worker_orphan_lease_reconciliation_pr8_8.js",
    "service_worker_reasoning_effort_slider_governance_pr8_8.js",
    "service_worker_instant_effort_slider_support_pr8_8.js",
)


def _source(name: str) -> str:
    return (EXT / name).read_text(encoding="utf-8")


def _run_harness() -> dict:
    prelude = r"""
const registrations = new Map();

function registerNativeTurnDiagnosticHandler(name, matches, handle) {
  if (registrations.has(name)) throw new Error("duplicate:" + name);
  registrations.set(name, { matches, handle });
}

let _pr88SelectionRecord = () => ({});
const PR88_INSTANT_EFFORT_SELECTION_SCHEMA_VERSION = 1;
const PR88_REASONING_EFFORT_SLIDER_SCHEMA_VERSION = 1;

function _pr88InstantEffortSupportConflict(message) {
  return message?.text != null;
}

globalThis.chrome = {
  storage: { local: {} },
  tabs: {},
  debugger: {}
};
"""
    epilogue = r"""
_pr88ReconcileOrphanLease = async () => ({ probe: "orphan-reconcile" });
_pr88EffortProbe = async () => ({ probe: "reasoning-topology" });

(async () => {
  const ordinary = { text: "ordinary product turn" };
  const ordinaryMatches = Array.from(registrations.entries())
    .filter(([, handler]) => handler.matches(ordinary) === true)
    .map(([name]) => name);

  const orphan = registrations.get("orphan-lease-reconciliation");
  const reasoning = registrations.get("reasoning-effort-characterization");
  const instant = registrations.get("instant-effort-support");

  const result = {
    names: Array.from(registrations.keys()).sort(),
    ordinaryMatches,
    orphanSupport: await orphan.handle({
      characterizeOrphanLeaseReconciliationSupport: true
    }),
    orphanReconcile: await orphan.handle({
      reconcileOrphanedBrowserAuthorityLease: true
    }),
    reasoningSupport: await reasoning.handle({
      characterizeReasoningEffortSliderSupport: true
    }),
    reasoningTopology: await reasoning.handle({
      characterizeReasoningEffortSliderTopology: true
    }),
    instantSupport: await instant.handle({
      characterizeInstantEffortSelectionSupport: true
    })
  };
  console.log(JSON.stringify(result));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
"""

    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(prelude)
        for worker in WORKERS:
            handle.write("\n")
            handle.write(_source(worker))
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


def test_explicit_control_diagnostics_bypass_ordinary_requests_and_route_exactly() -> None:
    result = _run_harness()

    assert result["names"] == [
        "instant-effort-support",
        "orphan-lease-reconciliation",
        "reasoning-effort-characterization",
    ]
    assert result["ordinaryMatches"] == []

    assert result["orphanSupport"]["orphanLeaseReconciliationSupported"] is True
    assert result["orphanSupport"]["zeroProductWrites"] is True
    assert result["orphanSupport"]["automaticRetry"] is False
    assert result["orphanReconcile"] == {"probe": "orphan-reconcile"}

    assert result["reasoningSupport"]["reasoningEffortSliderSupported"] is True
    assert result["reasoningSupport"]["selectionControlClickForbidden"] is True
    assert result["reasoningSupport"]["zeroProductWrites"] is True
    assert result["reasoningTopology"] == {"probe": "reasoning-topology"}

    assert result["instantSupport"]["instantEffortSelectionSupported"] is True
    assert result["instantSupport"]["advancedPickerClickForbidden"] is True
    assert result["instantSupport"]["modelControlClickForbidden"] is True
    assert result["instantSupport"]["automaticRetry"] is False
