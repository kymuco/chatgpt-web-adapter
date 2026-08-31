from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
REPAIR = EXT / "service_worker_rich_input_schema28_diagnostic_repair_pr9_2.js"


def _helper_block() -> str:
    text = REPAIR.read_text(encoding="utf-8")
    start = text.index("const PR92_SCHEMA28_DIAGNOSTIC_ROUTE_SAMPLE_MAX_MS")
    end = text.index("async function _pr92Schema28CommittedIdentityDiagnosticRepaired", start)
    return text[start:end]


def _run_node(script: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def test_schema28_route_sample_preserves_cleanup_reserve_without_calling_tabs_get():
    helpers = _helper_block()
    script = f"""
let tabGets = 0;
const chrome = {{ tabs: {{ get: async () => {{ tabGets += 1; throw new Error('must-not-run'); }} }} }};
const _pr92Schema7RunUntil = async (_deadlineAt, _label, fn) => fn();
const _pr92DeadlineRepairIsMissingTabError = () => false;
const conversationIdFromUrl = () => null;
{helpers}
(async () => {{
  const context = {{ deadlineAt: performance.now() + 5000 }};
  const result = await _pr92Schema28DiagnosticRouteSample(42, context, true);
  console.log(JSON.stringify({{ tabGets, result }}));
}})().catch((error) => {{ console.error(error); process.exit(1); }});
"""
    result = _run_node(script)
    assert result["tabGets"] == 0
    assert result["result"]["state"] == "unknown"
    assert result["result"]["skippedForCleanupReserve"] is True


def test_schema28_post_cleanup_presence_is_tri_state_and_not_cleanup_authority():
    helpers = _helper_block()
    script = f"""
let mode = 'present';
const chrome = {{ tabs: {{ get: async () => {{
  if (mode === 'present') return {{ id: 42, url: 'https://chatgpt.com/c/example' }};
  const error = new Error('No tab with id: 42.');
  error.missing = true;
  throw error;
}} }} }};
const _pr92Schema7RunUntil = async (_deadlineAt, _label, fn) => fn();
const _pr92DeadlineRepairIsMissingTabError = (error) => error?.missing === true;
const conversationIdFromUrl = (url) => url.includes('/c/') ? 'example' : null;
{helpers}
(async () => {{
  const presentContext = {{ deadlineAt: performance.now() + 5000 }};
  const present = await _pr92Schema28DiagnosticPostCleanupPresence(42, presentContext);
  mode = 'absent';
  const absentContext = {{ deadlineAt: performance.now() + 5000 }};
  const absent = await _pr92Schema28DiagnosticPostCleanupPresence(42, absentContext);
  console.log(JSON.stringify({{ present, absent }}));
}})().catch((error) => {{ console.error(error); process.exit(1); }});
"""
    result = _run_node(script)
    assert result["present"]["state"] == "present"
    assert result["present"]["routeConversationId"] == "example"
    assert result["absent"]["state"] == "absent"
    assert result["absent"]["url"] is None


def test_schema28_diagnostic_budget_is_monotonic_and_ignores_epoch_clock_jump():
    helpers = _helper_block()
    script = f"""
let tabGets = 0;
Date.now = () => 999999999999999;
const chrome = {{ tabs: {{ get: async () => {{
  tabGets += 1;
  return {{ id: 42, url: 'https://chatgpt.com/c/example' }};
}} }} }};
const _pr92Schema7RunUntil = async (deadlineAt, _label, fn) => {{
  if (!(deadlineAt > performance.now())) throw new Error('non-monotonic-deadline');
  return fn();
}};
const _pr92DeadlineRepairIsMissingTabError = () => false;
const conversationIdFromUrl = () => 'example';
{helpers}
(async () => {{
  const context = {{ deadlineAt: performance.now() + 12000 }};
  const route = await _pr92Schema28DiagnosticRouteSample(42, context, true);
  const post = await _pr92Schema28DiagnosticPostCleanupPresence(42, context);
  console.log(JSON.stringify({{ tabGets, route, post }}));
}})().catch((error) => {{ console.error(error); process.exit(1); }});
"""
    result = _run_node(script)
    assert result["tabGets"] == 2
    assert result["route"]["state"] == "present"
    assert result["route"]["skippedForCleanupReserve"] is False
    assert result["post"]["state"] == "present"


def test_schema28_diagnostic_repair_uses_monotonic_clock_domain_only():
    text = REPAIR.read_text(encoding="utf-8")
    helpers = _helper_block()
    assert "performance.now()" in helpers
    assert "Date.now()" not in helpers
    assert "context.deadlineAt - performance.now()" in helpers
    assert "performance.now() + budget" in helpers


def test_schema28_diagnostic_repair_keeps_write_authority_untouched():
    text = REPAIR.read_text(encoding="utf-8")
    assert "_pr92StageOfficialPageAttachments" not in text
    assert "button.click" not in text
    assert "Network.getResponseBody" not in text
    assert "extractSafeStreamMetadata" not in text
    assert "conversationWritePerformed: false" in text
    assert "attachmentStagingPerformed: false" in text
    assert "protectedSubmitAttempted: false" in text
    assert "routeConversationIdentityAuthoritative: false" in text
