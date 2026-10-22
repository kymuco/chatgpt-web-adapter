// Explicit, local-only auth synchronization. No tab creation or navigation.
// A caller must authorize the broker's auth_sync operation. The resulting
// credential payload stays on the local Native Messaging -> loopback path.
async function _cwaReadBrowserAuthSession() {
  const tabs = await chrome.tabs.query({ url: ["https://chatgpt.com/*"] });
  const tab = tabs.find((item) =>
    Number.isInteger(item?.id) &&
    item?.status === "complete" &&
    typeof item?.url === "string" &&
    /^https:\/\/chatgpt\.com(?:\/|$)/.test(item.url)
  );
  if (!tab) throw new Error("BROWSER_AUTH_EXISTING_TAB_REQUIRED");

  const debuggee = { tabId: tab.id };
  let attached = false;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    // The browser page owns the cookies, including HttpOnly/partition state.
    // Execute exactly one same-origin session GET, never a conversation GET.
    const expression = `(async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 12000);
      try {
        const response = await fetch("https://chatgpt.com/api/auth/session", {
          method: "GET",
          credentials: "include",
          cache: "no-store",
          headers: { accept: "application/json" },
          signal: controller.signal
        });
        if (response.status !== 200) {
          return { ok: false, reason: "BROWSER_AUTH_SESSION_HTTP_ERROR",
                   status: response.status };
        }
        const payload = await response.json();
        const accessToken = typeof payload?.accessToken === "string"
          ? payload.accessToken.trim() : "";
        if (!accessToken || accessToken.length > 100000) {
          return { ok: false, reason: "BROWSER_AUTH_ACCESS_TOKEN_MISSING" };
        }
        const sessionToken = typeof payload?.sessionToken === "string"
          ? payload.sessionToken.trim() : "";
        const expires = typeof payload?.expires === "string"
          ? payload.expires.slice(0, 512) : null;
        return {
          ok: true,
          accessToken,
          sessionToken: sessionToken.length <= 100000 ? sessionToken : "",
          expires
        };
      } catch {
        return { ok: false, reason: "BROWSER_AUTH_SESSION_REQUEST_FAILED" };
      } finally {
        clearTimeout(timer);
      }
    })()`;
    const evaluation = await chrome.debugger.sendCommand(
      debuggee, "Runtime.evaluate",
      { expression, awaitPromise: true, returnByValue: true }
    );
    const session = evaluation?.result?.value;
    if (evaluation?.exceptionDetails ||
        !session || session.ok !== true) {
      throw new Error(
        typeof session?.reason === "string" &&
        /^BROWSER_AUTH_[A-Z_]+$/.test(session.reason)
          ? session.reason : "BROWSER_AUTH_SESSION_UNAVAILABLE"
      );
    }

    const response = await chrome.debugger.sendCommand(
      debuggee, "Network.getCookies", { urls: ["https://chatgpt.com/"] }
    );
    const cookies = {};
    const browserCookies = [];
    for (const cookie of (Array.isArray(response?.cookies) ? response.cookies : [])) {
      const domain = typeof cookie?.domain === "string"
        ? cookie.domain.replace(/^\./, "").toLowerCase() : "";
      if (domain !== "chatgpt.com" && !domain.endsWith(".chatgpt.com")) continue;
      const name = cookie?.name;
      const value = cookie?.value;
      if (typeof name !== "string" || !name ||
          typeof value !== "string" || value.length > 100000) continue;
      if (browserCookies.length >= 100) break;
      cookies[name] = value;
      browserCookies.push({
        name, value, domain: cookie.domain,
        path: typeof cookie.path === "string" ? cookie.path : "/",
        secure: cookie.secure === true,
        http_only: cookie.httpOnly === true,
        ...(typeof cookie.expires === "number" && cookie.expires > 0
          ? { expires: cookie.expires } : {})
      });
    }
    if (!Object.keys(cookies).some((key) =>
      key === "__Secure-next-auth.session-token" ||
      key.startsWith("__Secure-next-auth.session-token.")
    )) {
      throw new Error("BROWSER_AUTH_SESSION_COOKIE_MISSING");
    }
    return {
      accessToken: session.accessToken,
      sessionToken: session.sessionToken,
      expires: session.expires,
      cookies, browserCookies
    };
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
  }
}

async function _cwaHandleBrowserAuthSync(message, port) {
  if (message?.protocol !== BRIDGE_PROTOCOL_VERSION ||
      message?.type !== "auth_sync") return false;
  const requestId = message.request_id;
  if (typeof requestId !== "string" || !requestId) return true;
  if (activeRequestId !== null) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION, type: "auth_sync_result",
      request_id: requestId, ok: false, reasonCode: "BROWSER_NATIVE_EXTENSION_BUSY"
    });
    return true;
  }
  activeRequestId = requestId;
  try {
    const session = await _cwaReadBrowserAuthSession();
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION, type: "auth_sync_result",
      request_id: requestId, ok: true, session
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : "";
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION, type: "auth_sync_result",
      request_id: requestId, ok: false,
      reasonCode: /^BROWSER_AUTH_[A-Z_]+$/.test(reason)
        ? reason : "BROWSER_AUTH_SYNC_FAILED"
    });
  } finally {
    activeRequestId = null;
  }
  return true;
}
