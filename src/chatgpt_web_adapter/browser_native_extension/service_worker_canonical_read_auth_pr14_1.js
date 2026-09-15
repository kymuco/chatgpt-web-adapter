const _pr141CanonicalFetchWithoutSessionBearer = _cwaCanonicalFetch;
const PR141_CANONICAL_AUTH_PATCH_KEY = "__cwaPr141CanonicalAuthPatch";
const PR141_CANONICAL_SESSION_MAX_CHARS = 262_144;
const PR141_CANONICAL_ACCESS_TOKEN_MAX_CHARS = 100_000;

function _pr141CanonicalSessionFailure(status, contentType, reasonCode) {
  return {
    ok: false,
    status: Number.isInteger(status) ? status : null,
    contentType: typeof contentType === "string" ? contentType : null,
    reasonCode,
    retryable: false
  };
}

async function _pr141EvaluateInRuntimeTab(tabId, expression) {
  const debuggee = { tabId };
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
      throw new Error("CANONICAL_READ_AUTH_RUNTIME_EVALUATION_FAILED");
    }
    const value = result?.result?.value;
    if (!value || typeof value !== "object") {
      throw new Error("CANONICAL_READ_AUTH_RUNTIME_RESULT_INVALID");
    }
    return value;
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

async function _pr141InstallCanonicalSessionBearer(
  tabId,
  conversationId,
  timeoutMs
) {
  const encodedConversationId = encodeURIComponent(conversationId);
  const currentPath = `/backend-api/conversations/${encodedConversationId}`;
  const legacyPath = `/backend-api/conversation/${encodedConversationId}`;
  const sessionEndpoint = `${CHATGPT_ORIGIN}/api/auth/session`;
  const patchLifetimeMs = Math.max(
    5_000,
    Math.min(Number(timeoutMs) + 5_000, 125_000)
  );
  const expression = `(async () => {
    const stateKey = ${JSON.stringify(PR141_CANONICAL_AUTH_PATCH_KEY)};
    const sessionEndpoint = ${JSON.stringify(sessionEndpoint)};
    const expectedPaths = new Set([
      ${JSON.stringify(currentPath)},
      ${JSON.stringify(legacyPath)}
    ]);
    const sessionMaxChars = ${JSON.stringify(PR141_CANONICAL_SESSION_MAX_CHARS)};
    const accessTokenMaxChars = ${JSON.stringify(PR141_CANONICAL_ACCESS_TOKEN_MAX_CHARS)};
    const patchLifetimeMs = ${JSON.stringify(patchLifetimeMs)};

    const stale = globalThis[stateKey];
    if (stale && typeof stale.restore === "function") {
      try { stale.restore(); } catch {}
    }
    if (globalThis[stateKey]) {
      return {
        ok: false,
        status: null,
        contentType: null,
        reasonCode: "CANONICAL_READ_AUTH_PATCH_BUSY",
        retryable: false
      };
    }

    const originalFetch = globalThis.fetch;
    if (typeof originalFetch !== "function") {
      return {
        ok: false,
        status: null,
        contentType: null,
        reasonCode: "CANONICAL_READ_AUTH_FETCH_UNAVAILABLE",
        retryable: false
      };
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), patchLifetimeMs);
    let sessionResponse;
    try {
      sessionResponse = await originalFetch.call(globalThis, sessionEndpoint, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
        headers: { accept: "application/json" },
        signal: controller.signal
      });
    } catch (error) {
      clearTimeout(timer);
      return {
        ok: false,
        status: null,
        contentType: null,
        reasonCode: error?.name === "AbortError"
          ? "CANONICAL_READ_TIMEOUT"
          : "CANONICAL_READ_SESSION_AUTH_NETWORK_ERROR",
        retryable: false
      };
    }
    clearTimeout(timer);

    const contentType = (
      sessionResponse.headers.get("content-type") || ""
    ).slice(0, 128);
    if (!sessionResponse.ok) {
      return {
        ok: false,
        status: sessionResponse.status,
        contentType,
        reasonCode: sessionResponse.status === 401
          ? "CANONICAL_READ_AUTHENTICATION_REQUIRED"
          : sessionResponse.status === 403
            ? "CANONICAL_READ_ACCESS_CHALLENGED"
            : "CANONICAL_READ_SESSION_AUTH_FAILED",
        retryable: false
      };
    }
    if (!contentType.toLowerCase().includes("json")) {
      return {
        ok: false,
        status: sessionResponse.status,
        contentType,
        reasonCode: "CANONICAL_READ_SESSION_AUTH_NON_JSON",
        retryable: false
      };
    }

    let sessionText;
    try {
      sessionText = await sessionResponse.text();
    } catch {
      return {
        ok: false,
        status: sessionResponse.status,
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
        status: sessionResponse.status,
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
        status: sessionResponse.status,
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
        status: sessionResponse.status,
        contentType,
        reasonCode: "CANONICAL_READ_SESSION_AUTH_TOKEN_REQUIRED",
        retryable: false
      };
    }

    const patchedFetch = function cwaPr141CanonicalAuthorizedFetch(input, init = {}) {
      let url;
      try {
        const rawUrl = input instanceof Request ? input.url : String(input);
        url = new URL(rawUrl, location.origin);
      } catch {
        return originalFetch.call(globalThis, input, init);
      }
      const method = String(
        init?.method || (input instanceof Request ? input.method : "GET") || "GET"
      ).toUpperCase();
      if (
        method !== "GET" ||
        url.origin !== location.origin ||
        !expectedPaths.has(url.pathname)
      ) {
        return originalFetch.call(globalThis, input, init);
      }

      const headers = new Headers(
        init?.headers || (input instanceof Request ? input.headers : undefined)
      );
      headers.set("authorization", `Bearer ${accessToken}`);
      return originalFetch.call(globalThis, input, { ...init, headers });
    };

    let restored = false;
    let expiry = null;
    const restore = () => {
      if (restored) return;
      restored = true;
      if (expiry !== null) clearTimeout(expiry);
      if (globalThis.fetch === patchedFetch) {
        globalThis.fetch = originalFetch;
      }
      try { delete globalThis[stateKey]; } catch {}
    };
    expiry = setTimeout(restore, patchLifetimeMs);
    Object.defineProperty(globalThis, stateKey, {
      value: Object.freeze({ restore }),
      configurable: true,
      enumerable: false,
      writable: false
    });
    globalThis.fetch = patchedFetch;

    return {
      ok: true,
      status: sessionResponse.status,
      contentType
    };
  })()`;

  return _pr141EvaluateInRuntimeTab(tabId, expression);
}

async function _pr141RestoreCanonicalSessionBearer(tabId) {
  const expression = `(() => {
    const stateKey = ${JSON.stringify(PR141_CANONICAL_AUTH_PATCH_KEY)};
    const state = globalThis[stateKey];
    if (!state) return { restored: true, alreadyAbsent: true };
    if (typeof state.restore !== "function") {
      return { restored: false, alreadyAbsent: false };
    }
    try {
      state.restore();
      return { restored: !globalThis[stateKey], alreadyAbsent: false };
    } catch {
      return { restored: false, alreadyAbsent: false };
    }
  })()`;
  const result = await _pr141EvaluateInRuntimeTab(tabId, expression);
  if (result.restored !== true) {
    throw new Error("CANONICAL_READ_AUTH_PATCH_RESTORE_FAILED");
  }
}

_cwaCanonicalFetch = async function _pr141CanonicalFetchWithSessionBearer(
  tabId,
  conversationId,
  timeoutMs,
  includeAllPages
) {
  const installed = await _pr141InstallCanonicalSessionBearer(
    tabId,
    conversationId,
    timeoutMs
  );
  if (installed.ok !== true) {
    return _pr141CanonicalSessionFailure(
      installed.status,
      installed.contentType,
      typeof installed.reasonCode === "string"
        ? installed.reasonCode
        : "CANONICAL_READ_SESSION_AUTH_FAILED"
    );
  }

  try {
    return await _pr141CanonicalFetchWithoutSessionBearer(
      tabId,
      conversationId,
      timeoutMs,
      includeAllPages
    );
  } finally {
    await _pr141RestoreCanonicalSessionBearer(tabId);
  }
};
