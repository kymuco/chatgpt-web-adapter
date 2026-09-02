const MAX_AUTH_COOKIE_COUNT = 256;
const MAX_AUTH_COOKIE_NAME_CHARS = 256;
const MAX_AUTH_COOKIE_VALUE_CHARS = 32_768;
const MAX_AUTH_COOKIE_DOMAIN_CHARS = 256;
const MAX_AUTH_COOKIE_PATH_CHARS = 2_048;
const MAX_AUTH_TOKEN_CHARS = 100_000;
const MAX_AUTH_PAYLOAD_BYTES = 750_000;

function _cwaCurrentChromeCookieDomainAllowed(value) {
  if (typeof value !== "string") return false;
  const domain = value.replace(/^\.+/, "").toLowerCase();
  return domain === "chatgpt.com" || domain.endsWith(".chatgpt.com");
}

function _cwaCurrentChromeBoundedString(value, maxChars, required = false) {
  if (typeof value !== "string") {
    if (required) throw new Error("CURRENT_CHROME_AUTH_PAYLOAD_INVALID");
    return null;
  }
  const normalized = value.trim();
  if ((required && !normalized) || value.length > maxChars) {
    throw new Error("CURRENT_CHROME_AUTH_PAYLOAD_INVALID");
  }
  return value;
}

function _cwaCurrentChromeCookieRecord(cookie) {
  const name = _cwaCurrentChromeBoundedString(
    cookie?.name,
    MAX_AUTH_COOKIE_NAME_CHARS,
    true
  );
  const value = _cwaCurrentChromeBoundedString(
    cookie?.value,
    MAX_AUTH_COOKIE_VALUE_CHARS
  );
  const domain = _cwaCurrentChromeBoundedString(
    cookie?.domain,
    MAX_AUTH_COOKIE_DOMAIN_CHARS,
    true
  );
  const path = _cwaCurrentChromeBoundedString(
    cookie?.path || "/",
    MAX_AUTH_COOKIE_PATH_CHARS,
    true
  );
  if (value === null || !_cwaCurrentChromeCookieDomainAllowed(domain)) {
    throw new Error("CURRENT_CHROME_AUTH_PAYLOAD_INVALID");
  }
  const record = { name, value, domain, path };
  const fields = [
    ["secure", "secure"],
    ["httpOnly", "http_only"],
    ["sameSite", "same_site"],
    ["expires", "expires"],
    ["priority", "priority"],
    ["sameParty", "same_party"],
    ["sourceScheme", "source_scheme"],
    ["sourcePort", "source_port"]
  ];
  for (const [source, target] of fields) {
    const item = cookie?.[source];
    if (["string", "number", "boolean"].includes(typeof item)) {
      record[target] = item;
    }
  }
  return record;
}

async function _cwaCurrentChromeSession(debuggee) {
  const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
    expression: `fetch('/api/auth/session', {credentials: 'include', cache: 'no-store'})
      .then(async (response) => {
        let body = null;
        try { body = await response.json(); } catch {}
        return {
          status: response.status,
          accessToken: body && typeof body.accessToken === 'string' ? body.accessToken : null,
          sessionToken: body && typeof body.sessionToken === 'string' ? body.sessionToken : null,
          expires: body ? body.expires : null
        };
      })
      .catch(() => ({status: 0, accessToken: null, sessionToken: null, expires: null}))`,
    returnByValue: true,
    awaitPromise: true
  });
  return result?.result?.value || null;
}

async function _cwaCurrentChromeUserAgent(debuggee) {
  const result = await chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {
    expression: "window.navigator.userAgent",
    returnByValue: true
  });
  return _cwaCurrentChromeBoundedString(result?.result?.value, 2_048) || "";
}

async function executeCurrentChromeAuth(message) {
  const timeoutMs = Math.max(
    1_000,
    Math.min(300_000, Number(message?.timeoutMs) || 300_000)
  );
  const startedAt = performance.now();
  let tabId = null;
  let debuggee = null;
  let attached = false;
  let captured = null;

  try {
    const tab = await chrome.tabs.create({ url: CHATGPT_ORIGIN + "/", active: true });
    if (!Number.isInteger(tab?.id)) {
      throw new Error("CURRENT_CHROME_AUTH_TAB_CREATE_FAILED");
    }
    tabId = tab.id;
    debuggee = { tabId };
    try {
      await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
      attached = true;
      await chrome.debugger.sendCommand(debuggee, "Runtime.enable");
      await chrome.debugger.sendCommand(debuggee, "Network.enable");
    } catch {
      throw new Error("CURRENT_CHROME_AUTH_DEBUGGER_ATTACH_FAILED");
    }

    while (elapsedMs(startedAt) < timeoutMs) {
      let session = null;
      try {
        session = await _cwaCurrentChromeSession(debuggee);
      } catch {
        session = null;
      }
      if (
        session?.status === 200 &&
        typeof session.accessToken === "string" &&
        session.accessToken.trim()
      ) {
        const accessToken = _cwaCurrentChromeBoundedString(
          session.accessToken,
          MAX_AUTH_TOKEN_CHARS,
          true
        );
        const sessionToken = _cwaCurrentChromeBoundedString(
          session.sessionToken,
          MAX_AUTH_TOKEN_CHARS
        );
        const cookieResult = await chrome.debugger.sendCommand(
          debuggee,
          "Network.getCookies",
          { urls: [CHATGPT_ORIGIN + "/"] }
        );
        const rawCookies = Array.isArray(cookieResult?.cookies)
          ? cookieResult.cookies
          : [];
        if (rawCookies.length > MAX_AUTH_COOKIE_COUNT) {
          throw new Error("CURRENT_CHROME_AUTH_PAYLOAD_INVALID");
        }
        const browserCookies = rawCookies.map(_cwaCurrentChromeCookieRecord);
        const hasSessionCookie = browserCookies.some((cookie) =>
          cookie.name === "__Secure-next-auth.session-token" ||
          cookie.name.startsWith("__Secure-next-auth.session-token.")
        );
        if (!hasSessionCookie) {
          await sleep(500);
          continue;
        }
        const userAgent = await _cwaCurrentChromeUserAgent(debuggee);
        captured = {
          accessToken,
          sessionToken,
          expires: session.expires ?? null,
          browserCookies,
          userAgent,
          tabId
        };
        if (new TextEncoder().encode(JSON.stringify(captured)).length > MAX_AUTH_PAYLOAD_BYTES) {
          throw new Error("CURRENT_CHROME_AUTH_PAYLOAD_INVALID");
        }
        break;
      }
      await sleep(500);
    }
    if (!captured) throw new Error("CURRENT_CHROME_AUTH_TIMEOUT");
    return captured;
  } finally {
    if (attached && debuggee) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
    if (debuggee) {
      try {
        const targets = await chrome.debugger.getTargets();
        if (targets.some((target) => target.tabId === tabId && target.attached)) {
          throw new Error("CURRENT_CHROME_AUTH_DEBUGGER_ATTACHMENT_LEAK");
        }
      } catch (error) {
        if (error instanceof Error && error.message === "CURRENT_CHROME_AUTH_DEBUGGER_ATTACHMENT_LEAK") {
          throw error;
        }
      }
    }
    // Keep a timed-out login tab visible so the operator can inspect or finish
    // account recovery. Only the tab created by this successful operation closes.
    if (captured && Number.isInteger(tabId)) {
      try { await chrome.tabs.remove(tabId); } catch {}
    }
  }
}
