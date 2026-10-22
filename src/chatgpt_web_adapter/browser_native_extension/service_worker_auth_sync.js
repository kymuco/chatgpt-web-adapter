// Explicit, local-only auth synchronization from the extension service worker.
// No tabs, CDP debugger, navigation, browser launch, or message submission.
// Chrome's "cookies" API needs the cookies + chatgpt.com host permissions.
async function _cwaReadBrowserAuthSession() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  let session;
  try {
    const response = await fetch("https://chatgpt.com/api/auth/session", {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      headers: { accept: "application/json" },
      signal: controller.signal
    });
    if (response.status !== 200) {
      throw new Error("BROWSER_AUTH_SESSION_HTTP_ERROR");
    }
    const payload = await response.json();
    const accessToken = typeof payload?.accessToken === "string"
      ? payload.accessToken.trim() : "";
    if (!accessToken || accessToken.length > 100000) {
      throw new Error("BROWSER_AUTH_ACCESS_TOKEN_MISSING");
    }
    const sessionToken = typeof payload?.sessionToken === "string"
      ? payload.sessionToken.trim() : "";
    const expires = typeof payload?.expires === "string"
      ? payload.expires.slice(0, 512) : null;
    session = {
      accessToken,
      sessionToken: sessionToken.length <= 100000 ? sessionToken : "",
      expires
    };
  } catch (error) {
    if (error?.message?.startsWith("BROWSER_AUTH_")) throw error;
    throw new Error("BROWSER_AUTH_SESSION_REQUEST_FAILED");
  } finally {
    clearTimeout(timer);
  }

  let returnedCookies;
  try {
    returnedCookies = await chrome.cookies.getAll({ url: "https://chatgpt.com/" });
  } catch {
    throw new Error("BROWSER_AUTH_COOKIE_ACCESS_FAILED");
  }
  if (!Array.isArray(returnedCookies)) {
    throw new Error("BROWSER_AUTH_COOKIE_ACCESS_FAILED");
  }

  const cookies = {};
  const browserCookies = [];
  for (const cookie of returnedCookies) {
    const domain = typeof cookie?.domain === "string"
      ? cookie.domain.replace(/^\./, "").toLowerCase() : "";
    if (domain !== "chatgpt.com" && !domain.endsWith(".chatgpt.com")) continue;
    const name = cookie?.name;
    const value = cookie?.value;
    if (typeof name !== "string" || !name ||
        typeof value !== "string" || value.length > 100000) continue;
    if (browserCookies.length >= 100) break;
    // Multiple path-scoped cookies can share a name; the cookie most specific
    // to the ChatGPT origin wins for the exported direct-HTTP cookie mapping.
    if (Object.prototype.hasOwnProperty.call(cookies, name)) continue;
    cookies[name] = value;
    browserCookies.push({
      name, value, domain: cookie.domain,
      path: typeof cookie.path === "string" ? cookie.path : "/",
      secure: cookie.secure === true,
      http_only: cookie.httpOnly === true,
      ...(typeof cookie.expirationDate === "number" && cookie.expirationDate > 0
        ? { expires: cookie.expirationDate } : {})
    });
  }
  if (!Object.keys(cookies).some((key) =>
    key === "__Secure-next-auth.session-token" ||
    key.startsWith("__Secure-next-auth.session-token.")
  )) {
    throw new Error("BROWSER_AUTH_SESSION_COOKIE_MISSING");
  }
  return { ...session, cookies, browserCookies };
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
