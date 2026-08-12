# PR8.0 — Browser-Native ChatGPT Session Bridge Feasibility

This is a research-only probe for the proposed replacement of the current
browser-per-turn Sentinel capture path.

## Hypothesis

A Chrome extension can attach to an already authenticated `chatgpt.com` tab
through the supported `chrome.debugger` extension API and use CDP `Input` plus
`Network` domains to let the **official ChatGPT page** execute the turn.

The probe intentionally does **not**:

- read or export browser cookies;
- call ChatGPT protected conversation endpoints from the extension itself;
- extract or persist Sentinel / proof-of-work / Turnstile credentials;
- abort the page's conversation request;
- parse the rendered assistant DOM;
- launch a new Chromium process.

The page owns authentication, device state, security handshakes, conversation
creation, memory/personalization, and the protected write. The extension only
provides trusted browser input and observes the resulting network lifecycle.

## Manual smoke

1. Open normal Chrome and sign into `https://chatgpt.com/` as usual.
2. Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**,
   and select the `extension/` directory.
3. Keep one ChatGPT tab open. It may remain in the background.
4. Open the extension popup and run **Probe capabilities**.
5. Run **Send through official page** with the default marker prompt.
6. Verify:
   - no new browser process/window is launched;
   - the existing ChatGPT tab receives the prompt;
   - the conversation appears in normal ChatGPT history;
   - the assistant produces `SDK_BRIDGE_OK`;
   - diagnostics report `conversationRequestSeen=true` and a successful status;
   - the probe works while the ChatGPT tab is not foregrounded.

## Kill gates

The architecture is a PASS only if all of the following hold:

1. **Existing-session reuse:** no login or cookie import is required after the
   normal Chrome profile is already signed in.
2. **Zero browser launch:** one turn causes zero Chromium/Chrome process launches.
3. **Background execution:** the ChatGPT tab does not need to steal focus.
4. **Official protected write:** the page itself sends the conversation POST;
   no Sentinel credential leaves the page runtime.
5. **Conversation continuity:** the resulting conversation is visible and
   resumable in ordinary ChatGPT web/desktop history.
6. **Personalization parity:** a controlled new-chat test can access the same
   ChatGPT memory/reference-history behavior as a manually-created web chat.
7. **Repeatability:** at least 20 sequential turns complete without debugger
   attachment leaks, duplicate turns, or browser restarts.

If gates 1–4 fail, do not build Native Messaging plumbing. Re-evaluate WebView2
or another first-party-runtime host instead.

## Known constraints to test

- `chrome.debugger` is an explicit high-trust extension permission and Chrome
  shows a permission warning.
- Opening DevTools on the same tab can detach an extension debugger session.
- The response body of a streamed conversation may not remain available through
  `Network.getResponseBody`; that is not a write-path failure. Existing adapter
  read APIs can be used after the page completes the turn.
- The accessibility-tree composer lookup is preferred; a narrow DOM selector is
  retained only as a feasibility fallback and should be removed or hardened if
  the experiment graduates.

## Graduation target

A PASS leads to PR8.1:

`BrowserNativeTurnProvider` + local Native Messaging bridge + adapter client
integration. The current Zendriver Sentinel provider remains a compatibility
fallback until live parity is demonstrated.
