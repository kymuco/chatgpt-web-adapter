from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
CANONICAL = EXT / "service_worker_canonical_read_v2.js"
READ_DOMAIN = EXT / "service_worker_runtime_read.js"


def _source() -> str:
    return CANONICAL.read_text(encoding="utf-8")


def test_active_browser_canonical_read_uses_throttle_safe_v2() -> None:
    read_domain = READ_DOMAIN.read_text(encoding="utf-8")
    source = _source()

    assert 'importScripts("service_worker_canonical_read_v2.js");' in read_domain
    assert "CWA_CANONICAL_THROTTLE_MAX_RETRIES = 3" in source
    assert "CWA_CANONICAL_THROTTLE_BACKOFF_BASE_MS = 250" in source
    assert "CWA_CANONICAL_THROTTLE_BACKOFF_MAX_MS = 4_000" in source
    assert "CWA_CANONICAL_RETRY_AFTER_MAX_MS = 10_000" in source
    assert "CWA_CANONICAL_PAGE_PACE_MS = 75" in source


def test_429_retry_is_bounded_and_preserves_exact_page_url() -> None:
    source = _source()

    assert "response.status === 429 && retryThrottle" in source
    assert 'response.headers.get("retry-after")' in source
    assert 'reasonCode: "CANONICAL_READ_THROTTLE_EXHAUSTED"' in source
    assert "attempt >= throttleMaxRetries" in source
    assert "const pageUrl = currentUrl(cursor);" in source
    assert "const older = await fetchBytes(pageUrl, true, true);" in source
    assert "pages.push(older.payload);" in source


def test_only_idempotent_canonical_reads_receive_retry_and_pacing() -> None:
    source = _source()

    assert (
        "const fetchBytes = async (url, authorizeCurrent = false, retryThrottle = false)"
        in source
    )
    assert "const first = await fetchBytes(currentUrl(), true, true);" in source
    assert "const legacy = await fetchBytes(legacyEndpoint, false, false);" in source
    assert "if (pagePaceMs > 0) await sleep(pagePaceMs);" in source
    assert 'method: "GET"' in source
    assert 'method: "POST"' not in source


def test_throttle_exhaustion_never_claims_partial_history_complete() -> None:
    source = _source()

    exhausted = source.index('reasonCode: "CANONICAL_READ_THROTTLE_EXHAUSTED"')
    merge = source.index("const mergedMessages = [];")
    assert exhausted < merge
    assert "if (older.ok !== true) return older;" in source
    assert (
        "const mergedPayload = { ...first.payload, messages: mergedMessages };"
        in source
    )


def _node_throttle_harness(mode: str) -> dict:
    """Run the actual page-evaluation flow under a deterministic virtual clock."""
    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const mode = process.argv[2];
let now = 0;
let nextTimer = 0;
const timers = new Map();
const controllers = [];
const requests = [];
let manuallyAborted = false;

const setFakeTimeout = (fn, delay) => {
  const id = ++nextTimer;
  timers.set(id, { fn, at: now + Number(delay), delay: Number(delay) });
  return id;
};
const clearFakeTimeout = (id) => { timers.delete(id); };
class TrackedController extends AbortController {
  constructor() { super(); controllers.push(this); }
}

const response = (status, body, retryAfter = null) => {
  const bytes = Buffer.from(JSON.stringify(body), "utf8");
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get(name) {
        if (name.toLowerCase() === "content-type") return "application/json";
        if (name.toLowerCase() === "retry-after") return retryAfter;
        return null;
      }
    },
    async arrayBuffer() {
      return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    },
    async text() { return bytes.toString("utf8"); }
  };
};

const page = {
  AbortController: TrackedController,
  setTimeout: setFakeTimeout,
  clearTimeout: clearFakeTimeout,
  performance: { now: () => now },
  URL, Headers, TextEncoder, TextDecoder, Uint8Array,
  crypto: { subtle: { digest: async () => new Uint8Array(32).buffer } },
  btoa: (text) => Buffer.from(text, "binary").toString("base64"),
  fetch: async (url, options) => {
    const parsed = new URL(String(url));
    if (options?.signal?.aborted) {
      const error = new Error("aborted");
      error.name = "AbortError";
      throw error;
    }
    if (parsed.pathname === "/api/auth/session") {
      return response(200, { accessToken: "private-test-token" });
    }
    if (parsed.pathname !== "/backend-api/conversations/conversation-1") {
      throw new Error("unexpected read endpoint");
    }
    requests.push({ url: String(url), at: now });
    const before = parsed.searchParams.get("before");
    if (mode === "cursor") {
      if (before === null) {
        return response(200, {
          conversation_id: "conversation-1",
          messages: [{ id: "new" }],
          page_info: { has_previous_page: true, start_cursor: "exact-cursor" }
        });
      }
      if (before !== "exact-cursor") throw new Error("cursor changed");
      if (requests.length === 2) return response(429, {}, "0.1");
      return response(200, {
        conversation_id: "conversation-1",
        messages: [{ id: "old" }],
        page_info: { has_previous_page: false }
      });
    }
    if (mode === "normal" && requests.length === 1) {
      return response(429, {}, "0.1");
    }
    if (mode === "deadline") return response(429, {}, "10");
    if (mode === "abort") return response(429, {}, "1");
    if (mode === "exhaust") return response(429, {}, "0.01");
    return response(200, {
      conversation_id: "conversation-1",
      messages: [],
      page_info: { has_previous_page: false }
    });
  }
};
vm.createContext(page);

async function drive(task) {
  let finished = false;
  let value;
  let failure;
  Promise.resolve(task).then(
    (result) => { finished = true; value = result; },
    (error) => { finished = true; failure = error; }
  );
  for (let steps = 0; steps < 200 && !finished; steps += 1) {
    for (let micro = 0; micro < 30; micro += 1) await Promise.resolve();
    if (finished) break;
    if (
      mode === "abort" && !manuallyAborted &&
      controllers.length === 1 &&
      [...timers.values()].some((timer) => timer.delay === 1000)
    ) {
      now = 80;
      manuallyAborted = true;
      controllers[0].abort();
      continue;
    }
    const pending = [...timers.entries()].sort((a, b) => a[1].at - b[1].at);
    if (!pending.length) throw new Error("virtual test stalled");
    const [id, timer] = pending[0];
    timers.delete(id);
    now = timer.at;
    timer.fn();
  }
  if (!finished) throw new Error("virtual test did not finish");
  if (failure) throw failure;
  return value;
}

const extension = {
  CHATGPT_ORIGIN: "https://chatgpt.com",
  CDP_PROTOCOL_VERSION: "1.3",
  chrome: {
    debugger: {
      attach: async () => {},
      detach: async () => {},
      sendCommand: async (_, method, args) => {
        if (method !== "Runtime.evaluate") throw new Error("unexpected command");
        const result = await drive(vm.runInContext(args.expression, page));
        return { result: { value: result } };
      }
    }
  }
};
vm.createContext(extension);
vm.runInContext(source, extension);
(async () => {
  const timeout = mode === "deadline" ? 250 : mode === "abort" ? 2000 : 1000;
  const expression = "_cwaCanonicalFetch(77, 'conversation-1', " +
    timeout + ", " + (mode === "cursor") + ")";
  const result = await vm.runInContext(expression, extension);
  process.stdout.write(JSON.stringify({
    result: {
      ok: result.ok,
      reasonCode: result.reasonCode || null,
      status: result.status,
      retryable: result.retryable || false
    },
    requests,
    elapsed: now,
    manuallyAborted
  }));
})().catch((error) => {
  process.stderr.write(String(error.stack || error));
  process.exitCode = 1;
});
"""
    completed = subprocess.run(
        ["node", "-e", script, str(CANONICAL), mode],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_429_backoff_within_deadline_retries_exact_url() -> None:
    result = _node_throttle_harness("normal")
    assert result["result"]["ok"] is True
    assert len(result["requests"]) == 2
    assert result["requests"][0]["url"] == result["requests"][1]["url"]
    assert [item["at"] for item in result["requests"]] == [0, 100]


def test_429_retry_preserves_older_page_cursor_and_completes() -> None:
    result = _node_throttle_harness("cursor")
    assert result["result"]["ok"] is True
    assert len(result["requests"]) == 3
    assert result["requests"][1]["url"] == result["requests"][2]["url"]
    assert "before=exact-cursor" in result["requests"][1]["url"]
    assert [item["at"] for item in result["requests"]] == [0, 75, 175]


def test_429_retry_after_exceeding_deadline_times_out_without_retry() -> None:
    result = _node_throttle_harness("deadline")
    assert result["result"]["reasonCode"] == "CANONICAL_READ_TIMEOUT"
    assert result["result"]["retryable"] is False
    assert len(result["requests"]) == 1
    assert result["elapsed"] == 250


def test_abort_during_429_wait_exits_immediately_without_retry() -> None:
    result = _node_throttle_harness("abort")
    assert result["manuallyAborted"] is True
    assert result["result"]["reasonCode"] == "CANONICAL_READ_TIMEOUT"
    assert len(result["requests"]) == 1
    assert result["elapsed"] == 80


def test_persistent_429_exhausts_existing_budget_before_deadline() -> None:
    result = _node_throttle_harness("exhaust")
    assert result["result"]["reasonCode"] == "CANONICAL_READ_THROTTLE_EXHAUSTED"
    assert result["result"]["status"] == 429
    assert result["result"]["retryable"] is True
    assert len(result["requests"]) == 4
    assert result["elapsed"] == 30
