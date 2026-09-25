from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
AUTHORITY = EXT / "service_worker_ordinary_text_identity_authority.js"
SEND_OWNER = EXT / "service_worker_send_command.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _run_node(source: str) -> dict[str, object]:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(source)
        path = Path(handle.name)
    try:
        completed = subprocess.run(
            ["node", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)
    finally:
        path.unlink(missing_ok=True)


def test_authority_precedes_explicit_send_command_owner() -> None:
    source = WRITE.read_text(encoding="utf-8")
    imports = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith("importScripts(")
    ]
    assert imports[-2:] == [
        'importScripts("service_worker_ordinary_text_identity_authority.js");',
        'importScripts("service_worker_send_command.js");',
    ]
    assert "ordinary_text_identity_error_boundary" not in source


def test_masked_legacy_error_restores_exact_ordinary_failure() -> None:
    authority = AUTHORITY.read_text(encoding="utf-8")
    source = f"""
let sendCommand = async () => ({{}});
let executeOfficialPageTurn = async () => ({{ conversationId: null }});
let executeNativeTurn = async function(message) {{
  if (message?.text === "ordinary") {{
    _cwaOrdinaryIdentityError(
      "ORDINARY_REQUEST_CORRELATION_UNRESOLVED",
      {{ requestCount: 2, unresolvedCount: 1 }}
    );
    throw new Error(
      "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED:" +
      "SCHEMA29:identityParserNotReached=true:" +
      "submitCorrelationDiagnosticsUnavailable=true"
    );
  }}
  throw new Error("NON_ORDINARY_FAILURE");
}};
function _pr92Schema29InspectRequestPostData() {{ return null; }}
function _pr92Schema29ExtractRequestBoundConversationMetadata() {{ return null; }}

{authority}

const _testPriorExecuteNativeTurn = executeNativeTurn;
executeNativeTurn = (message) =>
  _cwaOrdinaryIdentityExecuteNativeTurn(message, _testPriorExecuteNativeTurn);

(async () => {{
  let ordinaryError = null;
  let nonOrdinaryError = null;
  try {{
    await executeNativeTurn({{
      text: "ordinary",
      attachmentPaths: [],
      conversationMode: "normal",
      timeoutMs: 5000
    }});
  }} catch (error) {{
    ordinaryError = error instanceof Error ? error.message : String(error);
  }}
  try {{
    await executeNativeTurn({{
      text: "non-ordinary",
      attachmentPaths: ["attachment"],
      conversationMode: "normal",
      timeoutMs: 5000
    }});
  }} catch (error) {{
    nonOrdinaryError = error instanceof Error ? error.message : String(error);
  }}
  process.stdout.write(JSON.stringify({{ ordinaryError, nonOrdinaryError }}));
}})();
"""
    result = _run_node(source)
    assert result["ordinaryError"] == (
        "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED:"
        "ORDINARY_REQUEST_CORRELATION_UNRESOLVED:"
        "requestCount=2:unresolvedCount=1"
    )
    assert result["nonOrdinaryError"] == "NON_ORDINARY_FAILURE"


def test_preservation_changes_no_write_retry_or_fallback_authority() -> None:
    source = AUTHORITY.read_text(encoding="utf-8")
    preservation = source[source.index("  } catch (error) {") :]
    assert "throw new Error(exact);" in preservation
    assert "automaticWriteRetry" not in preservation
    assert "fallbackTransport" not in preservation
    assert "send_text" not in preservation
