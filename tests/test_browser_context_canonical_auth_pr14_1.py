from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
CANONICAL_V2 = EXT / "service_worker_canonical_read_v2.js"
READ_DOMAIN = EXT / "service_worker_runtime_read.js"
SESSION_AUTH_OVERLAY = EXT / "service_worker_canonical_read_session_auth.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_harness(mode: str) -> dict:
    source = _source(CANONICAL_V2)
    script = f"""
const mode = {json.dumps(mode)};
const events = [];

globalThis.onNativeMessage = async () => undefined;
globalThis.CDP_PROTOCOL_VERSION = "1.3";
globalThis.CHATGPT_ORIGIN = "https://chatgpt.com";
globalThis.activeRequestId = null;
globalThis.safePortPost = () => true;
globalThis.storedRuntimeTabId = async () => null;
globalThis.waitForTabComplete = async (tabId) => ({{ id: tabId, status: "complete" }});
globalThis.storeRuntimeTabId = async () => undefined;
globalThis.isChatGPTUrl = () => true;
globalThis._pr88StoredLeaseId = async () => null;
globalThis.crypto = require("node:crypto").webcrypto;
globalThis.btoa = (binary) => Buffer.from(binary, "binary").toString("base64");

class TestHeaders {{
  constructor(init = undefined) {{
    this.values = new Map();
    if (init && typeof init.get === "function") {{
      for (const name of ["accept", "authorization"]) {{
        const value = init.get(name);
        if (value !== null && value !== undefined) this.set(name, value);
      }}
    }} else if (init && typeof init === "object") {{
      for (const [name, value] of Object.entries(init)) this.set(name, value);
    }}
  }}
  set(name, value) {{
    this.values.set(String(name).toLowerCase(), String(value));
  }}
  get(name) {{
    return this.values.get(String(name).toLowerCase()) ?? null;
  }}
}}
globalThis.Headers = TestHeaders;

function authorizationOf(options) {{
  const headers = options?.headers;
  if (headers && typeof headers.get === "function") {{
    return headers.get("authorization");
  }}
  return new TestHeaders(headers).get("authorization");
}}

function jsonResponse(status, payload) {{
  const text = JSON.stringify(payload);
  const bytes = Buffer.from(text, "utf8");
  return {{
    ok: status >= 200 && status < 300,
    status,
    headers: {{
      get(name) {{
        return String(name).toLowerCase() === "content-type"
          ? "application/json"
          : null;
      }}
    }},
    async text() {{ return text; }},
    async arrayBuffer() {{
      return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    }}
  }};
}}

globalThis.fetch = async (url, options = {{}}) => {{
  const parsed = new URL(String(url));
  const authorization = authorizationOf(options);

  if (parsed.pathname === "/api/auth/session") {{
    events.push(["SESSION", authorization]);
    if (mode === "session401") return jsonResponse(401, {{ error: "unauthorized" }});
    return jsonResponse(200, {{ accessToken: "page-token-1" }});
  }}

  if (parsed.pathname === "/backend-api/conversations/conversation-1") {{
    events.push(["CURRENT", authorization]);
    if (authorization !== "Bearer page-token-1") {{
      return jsonResponse(401, {{ error: "bearer required" }});
    }}
    if (mode === "legacy") {{
      return jsonResponse(404, {{ error: "current unavailable" }});
    }}
    return jsonResponse(200, {{
      conversation_id: "conversation-1",
      messages: [],
      page_info: {{ has_previous_page: false }}
    }});
  }}

  if (parsed.pathname === "/backend-api/conversation/conversation-1") {{
    events.push(["LEGACY", authorization]);
    if (authorization !== null) {{
      return jsonResponse(500, {{ error: "legacy must stay cookie-only" }});
    }}
    return jsonResponse(200, {{ mapping: {{}}, current_node: null }});
  }}

  throw new Error("unexpected fetch: " + parsed.toString());
}};

globalThis.chrome = {{
  tabs: {{
    async get() {{ return {{ id: 77, status: "complete", url: "https://chatgpt.com/" }}; }},
    async create() {{ return {{ id: 77, status: "complete", url: "https://chatgpt.com/" }}; }}
  }},
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
      events.push(["EVALUATE", debuggee.tabId]);
      const value = await (0, eval)(params.expression);
      return {{ result: {{ value }} }};
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


def test_current_canonical_read_gets_page_session_bearer_in_same_evaluation() -> None:
    outcome = _run_harness("current")

    assert outcome["result"]["ok"] is True
    assert outcome["result"]["status"] == 200
    assert [event[0] for event in outcome["events"]] == [
        "ATTACH",
        "EVALUATE",
        "SESSION",
        "CURRENT",
        "DETACH",
    ]
    assert outcome["events"][2][1] is None
    assert outcome["events"][3][1] == "Bearer page-token-1"


def test_legacy_fallback_remains_cookie_only_after_authorized_current_404() -> None:
    outcome = _run_harness("legacy")

    assert outcome["result"]["ok"] is True
    assert outcome["result"]["status"] == 200
    assert [event[0] for event in outcome["events"]] == [
        "ATTACH",
        "EVALUATE",
        "SESSION",
        "CURRENT",
        "LEGACY",
        "DETACH",
    ]
    assert outcome["events"][3][1] == "Bearer page-token-1"
    assert outcome["events"][4][1] is None


def test_session_auth_failure_stops_before_any_conversation_get() -> None:
    outcome = _run_harness("session401")

    assert outcome["result"] == {
        "ok": False,
        "status": 401,
        "contentType": "application/json",
        "reasonCode": "CANONICAL_READ_AUTHENTICATION_REQUIRED",
        "retryable": False,
    }
    assert [event[0] for event in outcome["events"]] == [
        "ATTACH",
        "EVALUATE",
        "SESSION",
        "DETACH",
    ]


def test_canonical_session_auth_is_one_evaluation_and_never_exports_token() -> None:
    source = _source(CANONICAL_V2)
    read_domain = _source(READ_DOMAIN)

    assert "/api/auth/session" in source
    assert 'headers.set("authorization", "Bearer " + currentAccessToken);' in source
    assert "fetchBytes(currentUrl(), true, true)" in source
    assert "fetchBytes(pageUrl, true, true)" in source
    assert "fetchBytes(legacyEndpoint, false, false)" in source
    assert "currentAccessToken = null;" in source
    assert "globalThis.fetch =" not in source

    assert _source(READ_DOMAIN).count("importScripts(") == 3
    assert "service_worker_message_inspection.js" in read_domain
    assert "service_worker_canonical_read_session_auth.js" not in read_domain
    assert not SESSION_AUTH_OVERLAY.exists()

    # The access token exists only in the generated page-evaluation closure. It is
    # not returned through the Native Messaging result or written to storage/logs.
    assert "accessToken:" not in source
    assert "chrome.storage" not in source
    assert "console." not in source
