from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
BOUNDARY = EXT / "service_worker_ordinary_text_identity_error_boundary.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _run_node(source: str) -> dict[str, object]:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
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


def test_error_boundary_is_final_write_domain_layer() -> None:
    source = WRITE.read_text(encoding="utf-8")
    imports = [line.strip() for line in source.splitlines() if line.strip().startswith("importScripts(")]
    assert imports[-2:] == [
        'importScripts("service_worker_ordinary_text_identity_authority.js");',
        'importScripts("service_worker_ordinary_text_identity_error_boundary.js");',
    ]


def test_masked_legacy_error_restores_exact_ordinary_failure() -> None:
    boundary = BOUNDARY.read_text(encoding="utf-8")
    source = f"""
const CWA_ORDINARY_IDENTITY_COMMITTED_ERROR =
  "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED";
function _cwaOrdinaryIdentityEligible(message) {{
  return message?.ordinary === true;
}}
function _cwaOrdinaryIdentityError(suffix, diagnostics = null) {{
  let detail = `${{CWA_ORDINARY_IDENTITY_COMMITTED_ERROR}}:${{suffix}}`;
  if (diagnostics) {{
    for (const [key, value] of Object.entries(diagnostics)) {{
      if (typeof value === "boolean" || Number.isFinite(value)) {{
        detail += `:${{key}}=${{value}}`;
      }}
    }}
  }}
  return new Error(detail);
}}
let executeNativeTurn = async function(message) {{
  if (message?.ordinary === true) {{
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

{boundary}

(async () => {{
  let ordinaryError = null;
  let nonOrdinaryError = null;
  try {{
    await executeNativeTurn({{ ordinary: true }});
  }} catch (error) {{
    ordinaryError = error instanceof Error ? error.message : String(error);
  }}
  try {{
    await executeNativeTurn({{ ordinary: false }});
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


def test_boundary_does_not_create_retry_or_fallback_authority() -> None:
    source = BOUNDARY.read_text(encoding="utf-8")
    lowered = source.lower()
    assert "retry" in lowered
    assert "fallback" in lowered
    assert "automaticretry" not in lowered
    assert "fallbacktransport" not in lowered
    assert "send_text" not in lowered
    assert "sendcommand(" not in lowered
