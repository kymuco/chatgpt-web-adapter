from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
REPAIR = EXT / "service_worker_canonical_read_auth_pr14_1.js"
READ_DOMAIN = EXT / "service_worker_runtime_read.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_harness(install_result: dict) -> dict:
    source = _source(REPAIR)
    script = f"""
const installResult = {json.dumps(install_result)};
const events = [];

globalThis.CDP_PROTOCOL_VERSION = "1.3";
globalThis.CHATGPT_ORIGIN = "https://chatgpt.com";
globalThis._cwaCanonicalFetch = async (...args) => {{
  events.push(["PRIOR_FETCH", ...args]);
  return {{ ok: true, status: 200, contentType: "application/json" }};
}};

globalThis.chrome = {{
  debugger: {{
    async attach(debuggee, version) {{
      events.push(["ATTACH", debuggee.tabId, version]);
    }},
    async detach(debuggee) {{
      events.push(["DETACH", debuggee.tabId]);
    }},
    async sendCommand(debuggee, method, params) {{
      if (method !== "Runtime.evaluate") {{
        throw new Error(`unexpected command: ${{method}}`);
      }}
      if (params.expression.includes("alreadyAbsent")) {{
        events.push(["RESTORE_EVAL", debuggee.tabId]);
        return {{ result: {{ value: {{ restored: true, alreadyAbsent: false }} }} }};
      }}
      events.push(["INSTALL_EVAL", debuggee.tabId]);
      return {{ result: {{ value: installResult }} }};
    }}
  }}
}};

{source}

(async () => {{
  const result = await _cwaCanonicalFetch(
    77,
    "conversation-1",
    30000,
    false
  );
  process.stdout.write(JSON.stringify({{ result, events }}));
}})().catch((error) => {{
  process.stderr.write(String(error?.stack || error));
  process.exitCode = 1;
}});
"""
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_canonical_auth_repair_installs_before_read_and_restores_after() -> None:
    outcome = _run_harness(
        {"ok": True, "status": 200, "contentType": "application/json"}
    )

    assert outcome["result"]["ok"] is True
    labels = [event[0] for event in outcome["events"]]
    assert labels == [
        "ATTACH",
        "INSTALL_EVAL",
        "DETACH",
        "PRIOR_FETCH",
        "ATTACH",
        "RESTORE_EVAL",
        "DETACH",
    ]


def test_canonical_auth_repair_fails_closed_before_backend_read() -> None:
    outcome = _run_harness(
        {
            "ok": False,
            "status": 401,
            "contentType": "application/json",
            "reasonCode": "CANONICAL_READ_AUTHENTICATION_REQUIRED",
            "retryable": False,
        }
    )

    assert outcome["result"] == {
        "ok": False,
        "status": 401,
        "contentType": "application/json",
        "reasonCode": "CANONICAL_READ_AUTHENTICATION_REQUIRED",
        "retryable": False,
    }
    assert all(event[0] != "PRIOR_FETCH" for event in outcome["events"])
    assert all(event[0] != "RESTORE_EVAL" for event in outcome["events"])


def test_canonical_auth_repair_keeps_credential_inside_page_scope() -> None:
    source = _source(REPAIR)
    read_domain = _source(READ_DOMAIN)

    canonical_import = 'importScripts("service_worker_canonical_read_v2.js");'
    auth_import = 'importScripts("service_worker_canonical_read_auth_pr14_1.js");'
    assert read_domain.index(canonical_import) < read_domain.index(auth_import)

    assert "/api/auth/session" in source
    assert "expectedPaths.has(url.pathname)" in source
    assert 'method !== "GET"' in source
    assert 'headers.set("authorization", "Bearer " + accessToken);' in source
    assert "globalThis.fetch = patchedFetch;" in source
    assert "setTimeout(restore, patchLifetimeMs)" in source
    assert "CANONICAL_READ_AUTH_PATCH_RESTORE_FAILED" in source

    # The page token is consumed by a closure. The overlay has no native-message,
    # logging, storage or port path that could export credential material.
    assert "safePortPost" not in source
    assert "postNative" not in source
    assert "chrome.storage" not in source
    assert "console." not in source
