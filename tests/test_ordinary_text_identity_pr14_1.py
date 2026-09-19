from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
BASE = EXT / "service_worker.js"
AUTHORITY = EXT / "service_worker_ordinary_text_identity_authority.js"
WRITE = EXT / "service_worker_runtime_write.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _valid_post_data(text: str, conversation_id: str | None = None) -> str:
    payload: dict[str, object] = {
        "action": "next",
        "messages": [
            {
                "id": "client-message-1",
                "author": {"role": "user"},
                "content": {"parts": [text]},
            }
        ],
    }
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    return json.dumps(payload)


def _sse(*conversation_ids: str) -> str:
    return "".join(
        f"data: {json.dumps({'conversation_id': value, 'type': 'message_marker'})}\n\n"
        for value in conversation_ids
    )


def _run_harness(scenario: dict) -> dict:
    authority = _source(AUTHORITY)
    scenario_json = json.dumps(scenario)
    prelude = r"""
const scenario = __SCENARIO__;
const events = [];
const listeners = [];

if (typeof globalThis.atob !== "function") {
  globalThis.atob = (value) => Buffer.from(value, "base64").toString("binary");
}
if (typeof globalThis.btoa !== "function") {
  globalThis.btoa = (value) => Buffer.from(value, "binary").toString("base64");
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function emit(method, params) {
  for (const listener of [...listeners]) {
    listener({ tabId: 1 }, method, params);
  }
}

globalThis.chrome = {
  debugger: {
    onEvent: {
      addListener(listener) { listeners.push(listener); },
      removeListener(listener) {
        const index = listeners.indexOf(listener);
        if (index >= 0) listeners.splice(index, 1);
      }
    },
    async sendCommand(debuggee, method, params) {
      events.push(method);
      if (method === "Network.getRequestPostData") {
        if (scenario.lookupReject) throw new Error("post-data unavailable");
        if (scenario.lookupDelayMs) await delay(scenario.lookupDelayMs);
        events.push("POST_DATA_RESOLVED");
        return { postData: scenario.lookupPostData, base64Encoded: false };
      }
      if (method === "Network.streamResourceContent") {
        if (scenario.streamUnsupported) throw new Error("stream unsupported");
        events.push("STREAM_ENABLED");
        return {
          bufferedData: Buffer.from(scenario.streamBody || "", "utf8").toString("base64")
        };
      }
      if (method === "Network.getResponseBody") {
        events.push("RESPONSE_BODY_READ");
        return { body: scenario.responseBody || "", base64Encoded: false };
      }
      throw new Error(`unexpected debugger command: ${method}`);
    }
  }
};

globalThis.isConversationWrite = (url, method) => (
  method === "POST" && typeof url === "string" && url.includes("/conversation")
);

globalThis._pr92Schema28DecodeResponseBody = (body, base64Encoded) => {
  if (typeof body !== "string") return null;
  if (!base64Encoded) return body;
  return Buffer.from(body, "base64").toString("utf8");
};

function _mockText(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

globalThis._pr92Schema29InspectRequestPostData = (
  postData,
  expectedText,
  expectedAttachmentCount,
  expectedConversationId
) => {
  const diagnostics = {
    postDataPresent: typeof postData === "string" && postData.length > 0,
    requestJsonParsed: false,
    actionNext: false,
    conversationIdentityMatches: false,
    userMessageCount: 0,
    userMessageIdCount: 0,
    userMessageIdentityClassified: false,
    exactTextUserMessageCount: 0,
    exactRichUserMessageCount: 0,
    requestMessageIdPresent: false,
    attachmentCountsMatch: expectedAttachmentCount === 0
  };
  if (!diagnostics.postDataPresent) {
    return { matched: false, logicalMessageId: null, logicalUserMessageIds: [], diagnostics };
  }
  let payload;
  try { payload = JSON.parse(postData); } catch {
    return { matched: false, logicalMessageId: null, logicalUserMessageIds: [], diagnostics };
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return { matched: false, logicalMessageId: null, logicalUserMessageIds: [], diagnostics };
  }
  diagnostics.requestJsonParsed = true;
  diagnostics.actionNext = payload.action === "next";
  const requestConversationId = _mockText(payload.conversation_id);
  diagnostics.conversationIdentityMatches = expectedConversationId === null
    ? requestConversationId === null
    : requestConversationId === expectedConversationId;

  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  const logicalUserMessageIds = [];
  const exact = [];
  for (const message of messages) {
    if (message?.author?.role !== "user") continue;
    diagnostics.userMessageCount += 1;
    const messageId = _mockText(message?.id);
    if (messageId !== null) {
      diagnostics.userMessageIdCount += 1;
      logicalUserMessageIds.push(messageId);
    }
    const parts = Array.isArray(message?.content?.parts) ? message.content.parts : [];
    const text = parts.filter((part) => typeof part === "string").join("");
    if (
      diagnostics.actionNext &&
      diagnostics.conversationIdentityMatches &&
      text === expectedText
    ) {
      diagnostics.exactTextUserMessageCount += 1;
      if (messageId !== null && expectedAttachmentCount === 0) exact.push(messageId);
    }
  }
  diagnostics.userMessageIdentityClassified =
    diagnostics.userMessageCount === diagnostics.userMessageIdCount;
  diagnostics.exactRichUserMessageCount = exact.length;
  diagnostics.requestMessageIdPresent = exact.length === 1;
  return {
    matched: exact.length === 1,
    logicalMessageId: exact.length === 1 ? exact[0] : null,
    logicalUserMessageIds,
    diagnostics
  };
};

globalThis._pr92Schema29ExtractRequestBoundConversationMetadata = (
  body,
  base64Encoded
) => {
  const decoded = globalThis._pr92Schema28DecodeResponseBody(body, base64Encoded);
  const values = new Set();
  let parsedJsonDataRecords = 0;
  if (typeof decoded === "string") {
    for (const rawLine of decoded.split(/\r?\n/)) {
      if (!rawLine.startsWith("data:")) continue;
      const text = rawLine.slice(5).trim();
      if (!text || text === "[DONE]") continue;
      let payload;
      try { payload = JSON.parse(text); } catch { continue; }
      parsedJsonDataRecords += 1;
      const direct = _mockText(payload?.conversation_id);
      if (direct !== null) values.add(direct);
      const root = payload?.p === "" && payload?.o === "add" && payload?.v &&
        typeof payload.v === "object" && !Array.isArray(payload.v)
          ? _mockText(payload.v.conversation_id)
          : null;
      if (root !== null) values.add(root);
    }
  }
  return {
    conversationId: values.size === 1 ? Array.from(values)[0] : null,
    turnExchangeId: null,
    diagnostics: {
      parsedJsonDataRecords,
      conflictingConversationIds: values.size > 1
    }
  };
};

globalThis.sendCommand = async (debuggee, method, params) => {
  events.push(`SEND:${method}:${params?.type || ""}`);
  return {};
};

globalThis.executeOfficialPageTurn = async (args) => {
  if (scenario.preCommitRequest) {
    emit("Network.requestWillBeSent", {
      requestId: "background-before-commit",
      request: {
        url: "https://chatgpt.com/backend-api/conversation",
        method: "POST",
        postData: scenario.preCommitPostData,
        hasPostData: true
      }
    });
  }

  await sendCommand(
    { tabId: 1 },
    scenario.commitWithEnter ? "Input.dispatchKeyEvent" : "Input.dispatchMouseEvent",
    scenario.commitWithEnter
      ? { type: "keyDown", key: "Enter", code: "Enter" }
      : { type: "mouseReleased", button: "left" }
  );

  const request = {
    url: "https://chatgpt.com/backend-api/conversation",
    method: "POST",
    hasPostData: scenario.useLookup ? true : scenario.hasPostDataFalse ? false : true
  };
  if (!scenario.useLookup && !scenario.hasPostDataFalse) {
    request.postData = scenario.eventPostData;
  }
  emit("Network.requestWillBeSent", { requestId: "request-1", request });
  emit("Network.responseReceived", {
    requestId: "request-1",
    response: { status: 200, mimeType: "text/event-stream" }
  });
  if (scenario.loadingFinished) {
    emit("Network.loadingFinished", { requestId: "request-1" });
  }
  if (scenario.failAfterRequest) {
    throw new Error("CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED");
  }
  return {
    conversationId: "WEB:route-display-identity",
    responseStatus: 200,
    tabId: 1
  };
};

globalThis.executeNativeTurn = async (message) => executeOfficialPageTurn({
  tabId: 1,
  text: message.text,
  timeoutMs: message.timeoutMs
});
""".replace("__SCENARIO__", scenario_json)

    epilogue = r"""
(async () => {
  const message = {
    text: scenario.messageText,
    conversationId: scenario.requestedConversationId || null,
    attachmentPaths: [],
    conversationMode: "normal",
    timeoutMs: 5000
  };
  try {
    const result = await executeNativeTurn(message);
    console.log(JSON.stringify({ ok: true, result, events }));
  } catch (error) {
    console.log(JSON.stringify({
      ok: false,
      error: error instanceof Error ? error.message : String(error),
      postDelegationRequestCorrelationProven:
        error?.cwaPostDelegationRequestCorrelationProven === true,
      postDelegationUserMessageId:
        typeof error?.cwaPostDelegationUserMessageId === "string"
          ? error.cwaPostDelegationUserMessageId
          : null,
      postDelegationConversationId:
        typeof error?.cwaPostDelegationConversationId === "string"
          ? error.cwaPostDelegationConversationId
          : null,
      postDelegationRuntimeTabId:
        Number.isInteger(error?.cwaPostDelegationRuntimeTabId)
          ? error.cwaPostDelegationRuntimeTabId
          : null,
      events
    }));
  }
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
        handle.write(authority)
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


def test_authority_is_last_write_domain_layer_without_diagnostic_dependency() -> None:
    source = _source(WRITE)
    authority = 'importScripts("service_worker_ordinary_text_identity_authority.js");'
    commit = 'importScripts("service_worker_text_submit_commit_hardening_pr11_3.js");'

    assert authority in source
    assert source.index(commit) < source.index(authority)
    assert source.rstrip().endswith(authority)
    assert "identity_capture_diag" not in source


def test_turn_result_exports_only_bounded_post_delegation_identity_evidence() -> None:
    source = _source(BASE)
    assert "safeTurnFailureEvidence(error)" in source
    assert "postDelegationRequestCorrelationProven" in source
    assert "postDelegationUserMessageId" in source
    assert "postDelegationConversationId" in source
    assert "postDelegationRuntimeTabId" in source
    assert "postDelegationPrompt" not in source
    assert "postDelegationRequestBody" not in source


def test_authority_reuses_schema29_request_and_protocol_parsers() -> None:
    source = _source(AUTHORITY)
    assert "_pr92Schema29InspectRequestPostData(" in source
    assert "_pr92Schema29ExtractRequestBoundConversationMetadata(" in source
    assert "conversationIdFromUrl" not in source
    assert 'startsWith("WEB:")' not in source
    assert 'slice("WEB:".length)' not in source


def test_streaming_exact_request_promotes_protocol_identity_not_route() -> None:
    text = "ordinary identity streaming probe"
    expected = "6aa0c074-5d4c-83ec-b16d-92e095b71bf9"
    result = _run_harness(
        {
            "messageText": text,
            "eventPostData": _valid_post_data(text),
            "streamBody": _sse(expected),
        }
    )

    assert result["ok"] is True
    value = result["result"]
    assert value["conversationId"] == expected
    assert value["conversationId"] != "WEB:route-display-identity"
    assert value["ordinaryTextConversationIdentitySource"] == "sse_stream"
    assert value["routeConversationIdentityAuthoritative"] is False


def test_pre_commit_conversation_request_has_no_authority() -> None:
    text = "protected commit probe"
    expected = "7aa0c074-5d4c-83ec-b16d-92e095b71bf9"
    result = _run_harness(
        {
            "messageText": text,
            "preCommitRequest": True,
            "preCommitPostData": _valid_post_data("background request"),
            "eventPostData": _valid_post_data(text),
            "streamBody": _sse(expected),
        }
    )

    assert result["ok"] is True
    assert result["result"]["conversationId"] == expected
    assert result["result"]["ordinaryTextMatchingRequestCount"] == 1


def test_async_get_request_post_data_settles_before_identity_authority() -> None:
    text = "async request body probe"
    expected = "8aa0c074-5d4c-83ec-b16d-92e095b71bf9"
    result = _run_harness(
        {
            "messageText": text,
            "useLookup": True,
            "lookupDelayMs": 20,
            "lookupPostData": _valid_post_data(text),
            "streamBody": _sse(expected),
        }
    )

    assert result["ok"] is True
    events = result["events"]
    assert events.index("POST_DATA_RESOLVED") < events.index("STREAM_ENABLED")
    assert result["result"]["conversationId"] == expected


def test_aborted_correlated_continuation_retains_exact_request_bound_user_identity() -> (
    None
):
    text = "post delegation abort probe"
    requested = "6bb0c074-5d4c-83ec-b16d-92e095b71bf9"
    result = _run_harness(
        {
            "messageText": text,
            "requestedConversationId": requested,
            "eventPostData": _valid_post_data(text, requested),
            "failAfterRequest": True,
        }
    )

    assert result["ok"] is False
    assert result["error"] == "CHATGPT_CONVERSATION_REQUEST_FAILED:net::ERR_ABORTED"
    assert result["postDelegationRequestCorrelationProven"] is True
    assert result["postDelegationUserMessageId"] == "client-message-1"
    assert result["postDelegationConversationId"] == requested
    assert result["postDelegationRuntimeTabId"] == 1


def test_exact_request_body_mismatch_fails_closed() -> None:
    result = _run_harness(
        {
            "messageText": "intended text",
            "eventPostData": _valid_post_data("different text"),
            "streamBody": _sse("9aa0c074-5d4c-83ec-b16d-92e095b71bf9"),
        }
    )

    assert result["ok"] is False
    assert result["error"].startswith(
        "PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED:"
        "ORDINARY_REQUEST_CORRELATION_UNRESOLVED"
    )
    assert "Network.streamResourceContent" not in result["events"]


def test_unresolved_post_data_lookup_fails_closed() -> None:
    result = _run_harness(
        {
            "messageText": "lookup must resolve",
            "useLookup": True,
            "lookupReject": True,
            "lookupPostData": _valid_post_data("lookup must resolve"),
            "streamBody": _sse("aaa0c074-5d4c-83ec-b16d-92e095b71bf9"),
        }
    )

    assert result["ok"] is False
    assert "ORDINARY_REQUEST_CORRELATION_UNRESOLVED" in result["error"]
    assert "Network.streamResourceContent" not in result["events"]


def test_non_streaming_completed_request_uses_response_body_fallback() -> None:
    text = "response body fallback probe"
    expected = "baa0c074-5d4c-83ec-b16d-92e095b71bf9"
    result = _run_harness(
        {
            "messageText": text,
            "eventPostData": _valid_post_data(text),
            "streamUnsupported": True,
            "loadingFinished": True,
            "responseBody": _sse(expected),
        }
    )

    assert result["ok"] is True
    assert result["result"]["conversationId"] == expected
    assert result["result"]["ordinaryTextConversationIdentitySource"] == "response_body"
    assert "RESPONSE_BODY_READ" in result["events"]


def test_response_body_identity_conflict_fails_closed() -> None:
    text = "response conflict probe"
    result = _run_harness(
        {
            "messageText": text,
            "eventPostData": _valid_post_data(text),
            "streamUnsupported": True,
            "loadingFinished": True,
            "responseBody": _sse(
                "caa0c074-5d4c-83ec-b16d-92e095b71bf9",
                "daa0c074-5d4c-83ec-b16d-92e095b71bf9",
            ),
        }
    )

    assert result["ok"] is False
    assert result["error"].endswith(":RESPONSE_IDENTITY_CONFLICT")


def test_continuation_protocol_identity_mismatch_fails_closed() -> None:
    text = "continuation identity probe"
    requested = "eaa0c074-5d4c-83ec-b16d-92e095b71bf9"
    result = _run_harness(
        {
            "messageText": text,
            "requestedConversationId": requested,
            "eventPostData": _valid_post_data(text, requested),
            "streamBody": _sse("faa0c074-5d4c-83ec-b16d-92e095b71bf9"),
        }
    )

    assert result["ok"] is False
    assert result["error"].endswith(":SSE_REQUEST_IDENTITY_MISMATCH")


@pytest.mark.parametrize("commit_with_enter", [False, True])
def test_both_pr11_3_commit_boundaries_arm_authority(commit_with_enter: bool) -> None:
    text = "commit boundary probe"
    expected = "0ba0c074-5d4c-83ec-b16d-92e095b71bf9"
    result = _run_harness(
        {
            "messageText": text,
            "commitWithEnter": commit_with_enter,
            "eventPostData": _valid_post_data(text),
            "streamBody": _sse(expected),
        }
    )

    assert result["ok"] is True
    assert result["result"]["conversationId"] == expected
