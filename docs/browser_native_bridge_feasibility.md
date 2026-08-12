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

## Live evidence so far

The first live write smoke passed on an already authenticated normal Chrome
profile:

- `chrome.debugger` attached to an existing `chatgpt.com` tab;
- composer discovery used the accessibility tree;
- the official page emitted the conversation POST;
- the response was HTTP 200 with `text/event-stream`;
- the conversation became a normal ChatGPT history entry;
- no new Chromium process or separate login flow was required.

This establishes the core write-path feasibility. Background execution,
personalization parity, repeatability, and Python-SDK readback remain separate
gates.

## Manual smoke

1. Open normal Chrome and sign into `https://chatgpt.com/` as usual.
2. Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**,
   and select the `extension/` directory.
3. Keep a dedicated ChatGPT test tab open.
4. Open the extension popup and run **Probe capabilities**.
5. Choose the exact target ChatGPT tab from the selector. Sending without an
   explicit target is rejected.
6. For the background gate, make a different browser tab foreground while the
   selected ChatGPT test tab remains inactive.
7. Run **Send through official page** with the marker prompt.
8. Verify:
   - no new browser process/window is launched;
   - the selected ChatGPT tab receives the prompt without stealing focus;
   - the conversation appears in normal ChatGPT history;
   - diagnostics report `tabWasActive=false`,
     `conversationRequestSeen=true`, and a successful status;
   - no raw SSE body or transient resume credential is printed by the probe.

## Sensitive-response boundary

The initial feasibility build returned the raw response body for diagnostic
inspection. Live testing showed that this body can contain a transient resume
credential. The hardened probe therefore never returns raw SSE data.

`Network.getResponseBody` may be used transiently inside the service worker only
to locate the non-secret `stream_handoff` event. The worker extracts only:

- `conversationId`;
- `turnExchangeId`.

All other response body contents are discarded and never included in popup
results or diagnostics.

## Kill gates

The architecture is a PASS only if all of the following hold:

1. **Existing-session reuse:** no login or cookie import is required after the
   normal Chrome profile is already signed in. **PASS in first live smoke.**
2. **Zero browser launch:** one turn causes zero Chromium/Chrome process launches.
   **PASS in first live smoke.**
3. **Background execution:** the ChatGPT tab does not need to steal focus.
   **Pending hardened explicit-target smoke.**
4. **Official protected write:** the page itself sends the conversation POST;
   no Sentinel credential leaves the page runtime. **PASS in first live smoke.**
5. **Conversation continuity:** the resulting conversation is visible and
   resumable in ordinary ChatGPT web/desktop history. **Creation/history visibility PASS; readback parity pending.**
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
- Stream metadata extraction is secondary to the write path; a successful page
  turn remains valid even if `conversationId` or `turnExchangeId` cannot be
  recovered from retained network data.
- The accessibility-tree composer lookup is preferred; a narrow DOM selector is
  retained only as a feasibility fallback and should be removed or hardened if
  the experiment graduates.

## Graduation target

A PASS leads to PR8.1:

`BrowserNativeTurnProvider` + local Native Messaging bridge + adapter client
integration. The current Zendriver Sentinel provider remains a compatibility
fallback until live parity is demonstrated.
