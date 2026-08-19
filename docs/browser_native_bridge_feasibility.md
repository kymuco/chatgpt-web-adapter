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

Live testing on an already authenticated normal Chrome profile has established:

- `chrome.debugger` attaches to an existing `chatgpt.com` tab;
- composer discovery uses the accessibility tree in the observed environment;
- the official page emits the protected conversation POST;
- the response is HTTP 200 with `text/event-stream`;
- the conversation becomes a normal ChatGPT history entry;
- no new Chromium process or separate login flow is required;
- a selected inactive ChatGPT tab can execute the turn without stealing focus;
- the resulting conversation is immediately readable through the existing
  Python SDK `get_messages()` path;
- a bridge-created new chat reproduced ordinary account-side personalization in
  a controlled fact-recall parity test.

The remaining feasibility gate is 20-turn repeatability.

## Manual single-turn smoke

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

## PR8.0b repeatability harness

The popup includes **Run 20-turn background stress**. The selected ChatGPT tab
must be inactive before the run starts. The harness sends exactly these fixed
markers to one conversation:

```text
Reply with exactly: SDK_BRIDGE_STRESS_01
...
Reply with exactly: SDK_BRIDGE_STRESS_20
```

Each turn is serialized. Before typing the next marker, the worker waits for a
bounded composer-readiness condition so the test does not manufacture a race by
submitting while the previous short response is still generating.

For every turn the harness records only safe transport diagnostics:

- conversation request/response observation;
- HTTP status and elapsed time;
- composer targeting strategy and readiness wait;
- target-tab background state before/after the turn;
- debugger detach result and post-detach attachment state;
- conversation-id stability.

The harness fails closed on the first transport, focus, attachment, or
conversation-identity violation. It never returns raw SSE data.

After a 20/20 extension result, verify canonical ChatGPT history independently:

```bash
python examples/verify_browser_native_stress.py <conversation-id>
```

The verifier uses the normal SDK read path and requires exactly one matching user
marker and one final matching assistant marker for all 20 turns, with no missing
or duplicate markers and with the filtered marker sequence in order. Intermediate
assistant nodes are ignored unless their text exactly matches a stress marker.

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
   normal Chrome profile is already signed in. **PASS.**
2. **Zero browser launch:** one turn causes zero Chromium/Chrome process launches.
   **PASS.**
3. **Background execution:** the ChatGPT tab does not need to steal focus.
   **PASS.**
4. **Official protected write:** the page itself sends the conversation POST;
   no Sentinel credential leaves the page runtime. **PASS.**
5. **Conversation continuity:** the resulting conversation is visible and
   resumable in ordinary ChatGPT history and readable through the existing SDK.
   **PASS.**
6. **Personalization parity:** a controlled new-chat test can access the same
   account-side ChatGPT personalization behavior as a manually-created web chat.
   **PASS in controlled live parity smoke.**
7. **Repeatability:** at least 20 sequential turns complete without debugger
   attachment leaks, duplicate turns, conversation-id drift, browser restarts,
   or focus stealing. **Pending PR8.0b stress run.**

If gates 1–4 fail in a future compatibility regression, do not build on the
bridge blindly. Re-evaluate the first-party-runtime boundary before proceeding.

## Known constraints to test

- `chrome.debugger` is an explicit high-trust extension permission and Chrome
  shows a small visible indication while the debugger extension is active.
- Opening DevTools on the same tab can detach an extension debugger session.
- Stream metadata extraction is secondary to the write path; a successful page
  turn remains valid even if `conversationId` or `turnExchangeId` cannot be
  recovered from retained network data.
- The accessibility-tree composer lookup is preferred; a narrow DOM selector is
  retained only as a feasibility fallback and should be removed or hardened if
  the experiment graduates.
- The repeatability readiness barrier uses page-state signals only to avoid
  overlapping turns; it does not parse assistant output.

## Graduation target

A full PASS leads to PR8.1:

`BrowserNativeTurnProvider` + local Native Messaging bridge + adapter client
integration. The current Zendriver Sentinel provider remains a compatibility
fallback until live parity is demonstrated through the integrated path.
