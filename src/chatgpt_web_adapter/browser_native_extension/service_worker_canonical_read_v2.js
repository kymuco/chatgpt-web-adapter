const _cwaCanonicalPriorOnNativeMessage = onNativeMessage;
const CWA_CANONICAL_CHUNK_BASE64_CHARS = 600_000;
// Product-observed server query hint. It is not a message-count guarantee.
const CWA_CANONICAL_CURRENT_NUM_TURNS = 20;
const CWA_CANONICAL_MAX_PAGES = 100;
const CWA_CANONICAL_SESSION_MAX_CHARS = 262_144;
const CWA_CANONICAL_ACCESS_TOKEN_MAX_CHARS = 100_000;

function _cwaCanonicalConversationId(value) {
  const conversationId = typeof value === "string" ? value.trim() : "";
  if (
    !conversationId ||
    conversationId.includes("/") ||
    conversationId.includes("?") ||
    conversationId.includes("#")
  ) {
    throw new Error("CANONICAL_READ_CONVERSATION_ID_REQUIRED");
  }
  return conversationId;
}

function _cwaCanonicalStableReason(error) {
  const message = error instanceof Error ? error.message : String(error || "");
  return /^[A-Z0-9_]+$/.test(message)
    ? message
    : "CANONICAL_READ_BROWSER_ERROR";
}

async function _cwaCanonicalRuntimeTab() {
  const storedId = await storedRuntimeTabId();
  if (Number.isInteger(storedId)) {
    try {
      const tab = await chrome.tabs.get(storedId);
      if (isChatGPTUrl(tab?.url || "")) {
        return tab.status === "complete" ? tab : waitForTabComplete(storedId);
      }
    } catch {
      // Stale runtime-tab state is replaced without navigating another tab.
    }
  }

  const tab = await chrome.tabs.create({ url: `${CHATGPT_ORIGIN}/`, active: false });
  if (!Number.isInteger(tab?.id)) {
    throw new Error("CANONICAL_READ_RUNTIME_TAB_CREATE_FAILED");
  }
  await storeRuntimeTabId(tab.id);
  return waitForTabComplete(tab.id);
}

async function _cwaCanonicalFetch(
  tabId,
  conversationId,
  timeoutMs,
  includeAllPages
) {
  const debuggee = { tabId };
  const encodedConversationId = encodeURIComponent(conversationId);
  const currentEndpoint = `${CHATGPT_ORIGIN}/backend-api/conversations/${encodedConversationId}`;
  const legacyEndpoint = `${CHATGPT_ORIGIN}/backend-api/conversation/${encodedConversationId}`;
  const sessionEndpoint = `${CHATGPT_ORIGIN}/api/auth/session`;
  const expression = `(async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ${JSON.stringify(timeoutMs)});
    const currentNumTurns = ${JSON.stringify(CWA_CANONICAL_CURRENT_NUM_TURNS)};
    const maxPages = ${JSON.stringify(CWA_CANONICAL_MAX_PAGES)};
    const includeAllPages = ${JSON.stringify(includeAllPages === true)};
    const currentEndpoint = ${JSON.stringify(currentEndpoint)};
    const legacyEndpoint = ${JSON.stringify(legacyEndpoint)};
    const sessionEndpoint = ${JSON.stringify(sessionEndpoint)};
    const sessionMaxChars = ${JSON.stringify(CWA_CANONICAL_SESSION_MAX_CHARS)};
    const accessTokenMaxChars = ${JSON.stringify(CWA_CANONICAL_ACCESS_TOKEN_MAX_CHARS)};
    let currentAccessToken = null;

    const failureForResponse = (response, contentType) => ({
      ok: false,
      status: response.status,
      contentType,
      reasonCode: response.status === 404
        ? "CANONICAL_READ_NOT_VISIBLE"
        : response.status === 401
          ? "CANONICAL_READ_AUTHENTICATION_REQUIRED"
          : response.status === 403
            ? "CANONICAL_READ_ACCESS_CHALLENGED"
            : "CANONICAL_READ_HTTP_ERROR",
      retryable: response.status === 404
    });

    const loadCurrentAccessToken = async () => {
      if (currentAccessToken !== null) return { ok: true };

      const response = await fetch(sessionEndpoint, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
        headers: { accept: "application/json" },
        signal: controller.signal
      });
      const contentType = (
        response.headers.get("content-type") || ""
      ).slice(0, 128);
      if (!response.ok) {
        return {
          ok: false,
          status: response.status,
          contentType,
          reasonCode: response.status === 401
            ? "CANONICAL_READ_AUTHENTICATION_REQUIRED"
            : response.status === 403
              ? "CANONICAL_READ_ACCESS_CHALLENGED"
              : "CANONICAL_READ_SESSION_AUTH_FAILED",
          retryable: false
        };
      }
      if (!contentType.toLowerCase().includes("json")) {
        return {
          ok: false,
          status: response.status,
          contentType,
          reasonCode: "CANONICAL_READ_SESSION_AUTH_NON_JSON",
          retryable: false
        };
      }

      let sessionText;
      try {
        sessionText = await response.text();
      } catch {
        return {
          ok: false,
          status: response.status,
          contentType,
          reasonCode: "CANONICAL_READ_SESSION_AUTH_INVALID",
          retryable: false
        };
      }
      if (
        typeof sessionText !== "string" ||
        sessionText.length === 0 ||
        sessionText.length > sessionMaxChars
      ) {
        return {
          ok: false,
          status: response.status,
          contentType,
          reasonCode: "CANONICAL_READ_SESSION_AUTH_INVALID",
          retryable: false
        };
      }

      let sessionPayload;
      try {
        sessionPayload = JSON.parse(sessionText);
      } catch {
        return {
          ok: false,
          status: response.status,
          contentType,
          reasonCode: "CANONICAL_READ_SESSION_AUTH_INVALID",
          retryable: false
        };
      }
      const accessToken = typeof sessionPayload?.accessToken === "string"
        ? sessionPayload.accessToken.trim()
        : "";
      if (!accessToken || accessToken.length > accessTokenMaxChars) {
        return {
          ok: false,
          status: response.status,
          contentType,
          reasonCode: "CANONICAL_READ_SESSION_AUTH_TOKEN_REQUIRED",
          retryable: false
        };
      }

      currentAccessToken = accessToken;
      return { ok: true };
    };

    const fetchBytes = async (url, authorizeCurrent = false) => {
      const headers = new Headers({ accept: "application/json" });
      if (authorizeCurrent) {
        const auth = await loadCurrentAccessToken();
        if (auth.ok !== true) return auth;
        headers.set("authorization", "Bearer " + currentAccessToken);
      }

      const response = await fetch(url, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
        headers,
        signal: controller.signal
      });
      const contentType = (response.headers.get("content-type") || "").slice(0, 128);
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (!response.ok) {
        return { ...failureForResponse(response, contentType), bytes };
      }
      if (!contentType.toLowerCase().includes("json")) {
        return {
          ok: false,
          status: response.status,
          contentType,
          reasonCode: "CANONICAL_READ_NON_JSON",
          retryable: false,
          bytes
        };
      }
      let payload;
      try {
        payload = JSON.parse(new TextDecoder().decode(bytes));
      } catch {
        return {
          ok: false,
          status: response.status,
          contentType,
          reasonCode: "CANONICAL_READ_MALFORMED_JSON",
          retryable: false,
          bytes
        };
      }
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        return {
          ok: false,
          status: response.status,
          contentType,
          reasonCode: "CANONICAL_READ_JSON_OBJECT_REQUIRED",
          retryable: false,
          bytes
        };
      }
      return {
        ok: true,
        status: response.status,
        contentType,
        bytes,
        payload
      };
    };

    const currentUrl = (before = null) => {
      const url = new URL(currentEndpoint);
      url.searchParams.set("include_has_versions", "true");
      url.searchParams.set("num_turns", String(currentNumTurns));
      if (before !== null) url.searchParams.set("before", before);
      return url.toString();
    };

    const messageIdentity = (item) => {
      if (!item || typeof item !== "object" || Array.isArray(item)) return null;
      if (item.message && typeof item.message === "object" && !Array.isArray(item.message)) {
        return typeof item.message.id === "string" && item.message.id
          ? item.message.id
          : typeof item.id === "string" && item.id
            ? item.id
            : null;
      }
      return typeof item.id === "string" && item.id ? item.id : null;
    };

    const transfer = async (bytes, status, contentType) => {
      const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
      const sha256 = Array.from(
        digest,
        (value) => value.toString(16).padStart(2, "0")
      ).join("");
      let bodyBase64 = "";
      const binaryBlockBytes = 24_576;
      for (let offset = 0; offset < bytes.length; offset += binaryBlockBytes) {
        const block = bytes.subarray(offset, offset + binaryBlockBytes);
        let binary = "";
        for (let index = 0; index < block.length; index += 1) {
          binary += String.fromCharCode(block[index]);
        }
        bodyBase64 += btoa(binary);
      }
      return {
        ok: true,
        status,
        contentType,
        totalBytes: bytes.length,
        sha256,
        bodyBase64
      };
    };

    try {
      const first = await fetchBytes(currentUrl(), true);
      if (first.ok !== true) {
        if (first.status !== 404) return first;
        const legacy = await fetchBytes(legacyEndpoint, false);
        if (legacy.ok !== true) return legacy;
        if (!legacy.payload.mapping || typeof legacy.payload.mapping !== "object") {
          return {
            ok: false,
            status: legacy.status,
            contentType: legacy.contentType,
            reasonCode: "CANONICAL_READ_LEGACY_SHAPE_INVALID",
            retryable: false
          };
        }
        return transfer(legacy.bytes, legacy.status, legacy.contentType);
      }

      if (Array.isArray(first.payload.messages)) {
        if (!includeAllPages) {
          return transfer(first.bytes, first.status, first.contentType);
        }

        const pages = [first.payload];
        const seenCursors = new Set();
        while (true) {
          const page = pages[pages.length - 1];
          const pageInfo = page.page_info;
          if (!pageInfo || pageInfo.has_previous_page !== true) break;
          const cursor = typeof pageInfo.start_cursor === "string"
            ? pageInfo.start_cursor.trim()
            : "";
          if (!cursor) {
            return {
              ok: false,
              status: first.status,
              contentType: first.contentType,
              reasonCode: "CANONICAL_READ_PAGINATION_CURSOR_INVALID",
              retryable: false
            };
          }
          if (seenCursors.has(cursor)) {
            return {
              ok: false,
              status: first.status,
              contentType: first.contentType,
              reasonCode: "CANONICAL_READ_PAGINATION_CURSOR_REPEATED",
              retryable: false
            };
          }
          if (pages.length >= maxPages) {
            return {
              ok: false,
              status: first.status,
              contentType: first.contentType,
              reasonCode: "CANONICAL_READ_PAGINATION_LIMIT",
              retryable: false
            };
          }
          seenCursors.add(cursor);
          const older = await fetchBytes(currentUrl(cursor), true);
          if (older.ok !== true) return older;
          if (!Array.isArray(older.payload.messages)) {
            return {
              ok: false,
              status: older.status,
              contentType: older.contentType,
              reasonCode: "CANONICAL_READ_CURRENT_SHAPE_INVALID",
              retryable: false
            };
          }
          if (
            typeof first.payload.conversation_id === "string" &&
            typeof older.payload.conversation_id === "string" &&
            first.payload.conversation_id !== older.payload.conversation_id
          ) {
            return {
              ok: false,
              status: older.status,
              contentType: older.contentType,
              reasonCode: "CANONICAL_READ_PAGINATION_IDENTITY_MISMATCH",
              retryable: false
            };
          }
          pages.push(older.payload);
        }

        const mergedMessages = [];
        const seenMessageIds = new Set();
        for (const page of pages.slice().reverse()) {
          for (const item of page.messages) {
            const identity = messageIdentity(item);
            if (identity && seenMessageIds.has(identity)) continue;
            if (identity) seenMessageIds.add(identity);
            mergedMessages.push(item);
          }
        }
        const mergedPayload = { ...first.payload, messages: mergedMessages };
        const mergedBytes = new TextEncoder().encode(JSON.stringify(mergedPayload));
        return transfer(mergedBytes, first.status, first.contentType);
      }

      if (first.payload.mapping && typeof first.payload.mapping === "object") {
        return transfer(first.bytes, first.status, first.contentType);
      }

      return {
        ok: false,
        status: first.status,
        contentType: first.contentType,
        reasonCode: "CANONICAL_READ_CURRENT_SHAPE_INVALID",
        retryable: false
      };
    } catch (error) {
      return {
        ok: false,
        status: null,
        contentType: null,
        reasonCode: error?.name === "AbortError"
          ? "CANONICAL_READ_TIMEOUT"
          : "CANONICAL_READ_NETWORK_ERROR",
        retryable: false
      };
    } finally {
      currentAccessToken = null;
      clearTimeout(timer);
    }
  })()`;

  let attached = false;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true
    });
    if (result?.exceptionDetails) {
      throw new Error("CANONICAL_READ_RUNTIME_EVALUATION_FAILED");
    }
    const value = result?.result?.value;
    if (!value || typeof value !== "object") {
      throw new Error("CANONICAL_READ_RUNTIME_RESULT_INVALID");
    }
    return value;
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

async function _cwaCanonicalRead(message, port) {
  const requestId = message.request_id;
  const conversationId = _cwaCanonicalConversationId(message.conversationId);
  const timeoutMs = Number.isFinite(message.timeoutMs)
    ? Math.max(1_000, Math.min(Number(message.timeoutMs), 120_000))
    : 30_000;
  const leaseId =
    typeof message.browserAuthorityLeaseId === "string" &&
    message.browserAuthorityLeaseId.trim()
      ? message.browserAuthorityLeaseId.trim()
      : null;
  const includeAllPages = message.includeAllPages === true;

  if (leaseId !== null) {
    const storedLeaseId = await _pr88StoredLeaseId();
    if (storedLeaseId !== leaseId) {
      throw new Error("CANONICAL_READ_AUTHORITY_LEASE_MISMATCH");
    }
  }

  const tab = await _cwaCanonicalRuntimeTab();
  if (!Number.isInteger(tab?.id)) {
    throw new Error("CANONICAL_READ_RUNTIME_TAB_REQUIRED");
  }
  const fetched = await _cwaCanonicalFetch(
    tab.id,
    conversationId,
    timeoutMs,
    includeAllPages
  );
  if (fetched.ok !== true) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "canonical_read_result",
      request_id: requestId,
      ok: false,
      reasonCode: fetched.reasonCode,
      status: fetched.status,
      contentType: fetched.contentType,
      retryable: fetched.retryable === true
    });
    return;
  }

  const bodyBase64 = fetched.bodyBase64;
  if (
    typeof bodyBase64 !== "string" ||
    !/^[0-9a-f]{64}$/.test(fetched.sha256 || "")
  ) {
    throw new Error("CANONICAL_READ_TRANSFER_SOURCE_INVALID");
  }
  const chunkCount = Math.max(
    1,
    Math.ceil(bodyBase64.length / CWA_CANONICAL_CHUNK_BASE64_CHARS)
  );

  for (let chunkIndex = 0; chunkIndex < chunkCount; chunkIndex += 1) {
    const data = bodyBase64.slice(
      chunkIndex * CWA_CANONICAL_CHUNK_BASE64_CHARS,
      (chunkIndex + 1) * CWA_CANONICAL_CHUNK_BASE64_CHARS
    );
    if (!safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "canonical_read_chunk",
      request_id: requestId,
      chunkIndex,
      chunkCount,
      totalBytes: fetched.totalBytes,
      sha256: fetched.sha256,
      data
    })) {
      throw new Error("CANONICAL_READ_CHUNK_DELIVERY_FAILED");
    }
  }

  safePortPost(port, {
    protocol: BRIDGE_PROTOCOL_VERSION,
    type: "canonical_read_result",
    request_id: requestId,
    ok: true,
    status: fetched.status,
    contentType: fetched.contentType,
    chunkCount,
    totalBytes: fetched.totalBytes,
    sha256: fetched.sha256,
    browserAuthorityLeaseId: leaseId,
    runtimeTabId: tab.id
  });
}

onNativeMessage = async function _cwaOnNativeMessageWithCanonicalRead(message, port) {
  if (
    message?.protocol !== BRIDGE_PROTOCOL_VERSION ||
    message?.type !== "canonical_read"
  ) {
    return _cwaCanonicalPriorOnNativeMessage(message, port);
  }
  const requestId = message.request_id;
  if (typeof requestId !== "string" || !requestId) return;
  if (activeRequestId !== null) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "canonical_read_result",
      request_id: requestId,
      ok: false,
      reasonCode: "BROWSER_NATIVE_EXTENSION_BUSY",
      retryable: false
    });
    return;
  }

  activeRequestId = requestId;
  try {
    await _cwaCanonicalRead(message, port);
  } catch (error) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: "canonical_read_result",
      request_id: requestId,
      ok: false,
      reasonCode: _cwaCanonicalStableReason(error),
      retryable: false
    });
  } finally {
    activeRequestId = null;
  }
};
