from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = (
    ROOT
    / "src"
    / "chatgpt_web_adapter"
    / "browser_native_extension"
    / "service_worker.js"
)


def _dispatch_source() -> str:
    source = WORKER.read_text(encoding="utf-8")
    start = source.index("const nativeTurnDiagnosticHandlers = new Map();")
    end = source.index("function sleep(ms)", start)
    return source[start:end]


def _run_harness(epilogue: str) -> dict:
    prelude = """
const events = [];
async function executeNativeTurn(message) {
  events.push(`core:${message.kind || "unknown"}`);
  if (message.failCore === true) throw new Error("CORE_FAILURE");
  return { value: "core" };
}
"""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(prelude)
        handle.write("\n")
        handle.write(_dispatch_source())
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


def test_observers_preserve_wrapper_nesting_order() -> None:
    result = _run_harness(
        """
registerNativeTurnObserver("inner", {
  async before() { events.push("before:inner"); return "inner-context"; },
  async afterSuccess(_message, result, context) {
    events.push(`after:inner:${context}`);
    return { ...result, inner: true };
  },
  async finish(_message, context) {
    events.push(`finish:inner:${context}`);
  }
});
registerNativeTurnObserver("outer", {
  async before() { events.push("before:outer"); return "outer-context"; },
  async afterSuccess(_message, result, context) {
    events.push(`after:outer:${context}`);
    return { ...result, outer: true };
  },
  async finish(_message, context) {
    events.push(`finish:outer:${context}`);
  }
});

(async () => {
  const value = await dispatchNativeTurn({ kind: "ordinary" });
  console.log(JSON.stringify({ value, events }));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
"""
    )

    assert result["value"] == {"value": "core", "inner": True, "outer": True}
    assert result["events"] == [
        "before:outer",
        "before:inner",
        "core:ordinary",
        "after:inner:inner-context",
        "after:outer:outer-context",
        "finish:inner:inner-context",
        "finish:outer:outer-context",
    ]


def test_diagnostic_dispatch_bypasses_ordinary_turn_observers() -> None:
    result = _run_harness(
        """
registerNativeTurnObserver("ordinary-observer", {
  async before() { events.push("observer-before"); }
});
registerNativeTurnDiagnosticHandler(
  "probe",
  (message) => message.probe === true,
  async () => {
    events.push("diagnostic");
    return { diagnostic: true };
  }
);

(async () => {
  const value = await dispatchNativeTurn({ kind: "diagnostic", probe: true });
  console.log(JSON.stringify({ value, events }));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
"""
    )

    assert result["value"] == {"diagnostic": True}
    assert result["events"] == ["diagnostic"]


def test_observer_cleanup_cannot_replace_core_failure() -> None:
    result = _run_harness(
        """
registerNativeTurnObserver("inner", {
  async before() { events.push("before:inner"); return "inner-context"; },
  async finish() {
    events.push("finish:inner");
    throw new Error("CLEANUP_FAILURE");
  }
});
registerNativeTurnObserver("outer", {
  async before() { events.push("before:outer"); return "outer-context"; },
  async finish() { events.push("finish:outer"); }
});

(async () => {
  try {
    await dispatchNativeTurn({ kind: "ordinary", failCore: true });
  } catch (error) {
    console.log(JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
      events
    }));
    return;
  }
  console.log(JSON.stringify({ error: null, events }));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
"""
    )

    assert result["error"] == "CORE_FAILURE"
    assert result["events"] == [
        "before:outer",
        "before:inner",
        "core:ordinary",
        "finish:inner",
        "finish:outer",
    ]
