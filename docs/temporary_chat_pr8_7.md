# PR8.7 — Temporary Chat Product Semantics, Ephemeral Identity / Persistence Characterization and Fail-Closed Conversation-Mode Governance

_Status: live characterization stage; production Temporary Chat remains capability-gated_

_Date: 2026-08-15_

_Base: reviewed post-PR8 daily-use bridge direction_

## 1. Goal

PR8.7 establishes Temporary Chat as an evidence-backed product-runtime capability rather than inferring support from the existence of the feature in the ChatGPT UI.

The target is eventually to let callers request an ephemeral product turn explicitly, for example:

```python
runtime.send(
    prompt,
    conversation_mode="temporary",
)
```

but **production Temporary Chat is not enabled by this characterization commit**.

The current browser-owned capability remains:

```text
temporary_chat = UNKNOWN
```

until live evidence proves the required selection, identity, persistence, finality, and mode-isolation contracts.

## 2. Official product expectations versus adapter evidence

OpenAI's current Temporary Chat documentation states that Temporary Chats:

- are started from a new chat by selecting the Temporary control;
- do not appear in normal chat history;
- do not use or create memories for personalization;
- are not used to improve models;
- may still be retained for up to 30 days for safety purposes;
- continue to follow enabled Custom Instructions.

Current product references:

- https://help.openai.com/en/articles/8914046-temporary-chat-faq
- https://help.openai.com/en/articles/7730893-chatgpt-temporary-chat-faq

Those are **product expectations**, not proof that the current browser-owned adapter can select, observe, identify, read back, or isolate Temporary Chat correctly.

PR8.7 therefore separates:

```text
PRODUCT DOCUMENTATION
        !=
ADAPTER LIVE CONTRACT
```

## 3. First live question: can Temporary mode be selected and proven before any write?

The first characterization gate is deliberately narrow:

```text
T0
new-chat product page
    -> Temporary control can be found
    -> Temporary selected state can be observed explicitly
    -> selection can be performed without sending a chat message
    -> no conversation POST occurs
```

This gate comes before any production `conversation_mode="temporary"` send path.

Fail-closed rule:

> A future explicit Temporary request must never silently create a durable ordinary chat when Temporary selection cannot be proven before the write.

## 4. Isolated no-write probe

This commit adds a research/diagnostic probe:

```powershell
python -m chatgpt_web_adapter.temporary_chat_probe --timeout 30
```

The probe intentionally does **not** use the reusable production runtime tab.

It creates a dedicated isolated new-chat tab:

```text
create inactive https://chatgpt.com/
        |
        v
wait for ordinary composer readiness
        |
        v
find Temporary control using bounded visible button/accessibility fields
        |
        v
observe explicit selected-state attributes
        |
        +-- already explicitly selected -> record evidence
        |
        `-- otherwise click only the Temporary control
                  |
                  v
             re-observe explicit selected state
        |
        v
verify no conversation POST was observed
        |
        v
detach debugger
        |
        v
close isolated probe tab
```

No user prompt is inserted.

No assistant response is requested.

No conversation is intentionally created.

The normal production `executeNativeTurn()` path remains unchanged for every request that does not explicitly carry the internal diagnostic flag:

```text
probeTemporaryMode = true
```

## 5. Selection evidence is intentionally conservative

The probe does not infer Temporary mode merely because a button containing the word `Temporary` exists.

It first locates one visible control through bounded fields such as:

```text
visible text
aria-label
title
data-testid
```

Only the **field names that matched** are returned. Raw control text and raw DOM are not exported.

A selected state is considered proven only when an explicit state attribute is observed, such as:

```text
aria-pressed=true
aria-checked=true
aria-current=true
data-selected=true
data-state=on|checked|active|selected
```

CSS class names are not treated as authoritative selection evidence.

If more than one candidate control matches, the probe fails closed with:

```text
TEMPORARY_CHAT_CONTROL_AMBIGUOUS
```

rather than guessing which control to click.

If the control exists but no explicit selected-state signal can be proved after activation, the result remains:

```text
mode_selection_proven = false
```

That is useful live evidence. The selector/evidence model can then be repaired from observed current UI behavior instead of weakening the gate.

## 6. Privacy and product-boundary constraints

The PR8.7 probe returns only structural evidence.

It must not export:

```text
cookies
Authorization headers
Sentinel/protection credentials
Turnstile material
raw request headers
raw response bodies
raw DOM
prompt text
assistant text
conversation ids
message ids
```

It monitors the browser network only for the boolean question:

```text
Did any ordinary conversation POST occur during this no-write probe?
```

If the answer is yes, the probe fails as an invariant violation:

```text
TEMPORARY_CHAT_PROBE_UNEXPECTED_CONVERSATION_WRITE
```

## 7. Probe result schema

Example structural result shape:

```json
{
  "ok": true,
  "probe_context": "isolated_new_chat",
  "control_found": true,
  "candidate_count": 1,
  "selected_before": false,
  "selected_after": true,
  "mode_selection_proven": true,
  "selection_action": "cdp_control_click",
  "reason": "TEMPORARY_CHAT_SELECTION_PROVEN",
  "match_signals": ["text"],
  "selection_proof_signals": ["aria-pressed:true"],
  "conversation_write_observed": false,
  "tab_was_active": false,
  "tab_active_after": false,
  "tab_activated_during_probe": false,
  "foreground_activation_observed": false,
  "probe_tab_closed": true,
  "elapsed_ms": 1234
}
```

The exact live values are evidence, not expectations.

A probe exit code of `0` means selected-state evidence was proven.

Exit code `1` means the probe ran safely but selected-state evidence was not sufficient.

Exit code `2` means the diagnostic operation itself failed.

## 8. Why the probe uses a dedicated tab

The reviewed architecture requires conversation/product mode isolation.

A probe that toggled Temporary mode inside the reusable production runtime tab could accidentally contaminate the next ordinary durable turn if the UI mode is sticky.

Therefore this characterization stage uses:

```text
DEDICATED PROBE TAB
```

rather than:

```text
PRODUCTION RUNTIME TAB
```

and closes it after the probe.

This does not yet prove that Temporary mode is account-local, tab-local, conversation-local, or turn-local. Those scopes remain explicit PR8.7 experiment questions.

## 9. Remaining PR8.7 evidence matrix

A successful T0 probe is necessary but not sufficient to graduate the capability.

The remaining matrix is:

```text
T0  Temporary selected state can be proven before write
T1  ordinary text turn succeeds under proven Temporary mode
T2  terminal response/readback semantics are characterized
T3  identity semantics are characterized
T4  persistence/history behavior is characterized
T5  no normal durable fallback occurs when selection fails
T6  continuation behavior is characterized rather than assumed
T7  requested/observed conversation-mode provenance is defined
T8  TEMP -> NORMAL isolation is proven
T9  NORMAL -> TEMP isolation is proven
T10 cold/warm/runtime-tab recreation behavior is characterized
T11 capability moves UNKNOWN -> AVAILABLE only after the above evidence supports it
```

## 10. Identity and finality questions must remain open

Temporary Chat must not be forced into ordinary durable-chat assumptions.

PR8.7 must determine:

```text
Does a Temporary turn receive a conversation_id?
If yes, is it stable only during the turn or usable after completion?
Can canonical get_messages() observe it?
Can canonical get_status() prove terminal state?
Can attach_conversation() observe it?
Does it appear in ordinary history enumeration?
What survives runtime-tab close/recreation?
What survives browser restart?
```

If Temporary Chat exposes a different authoritative observation mechanism, the product-runtime contract should model the actual ephemeral semantics rather than inventing durable identity.

## 11. Production conversation-mode API is intentionally deferred to the next PR8.7 commit

This first commit does **not** add a public `conversation_mode` parameter to `ChatGPTProductRuntime.send()`.

Reason:

```text
selection mechanism not yet live-proven
+
identity/readback semantics not yet characterized
=
do not expose a production promise yet
```

After the live probe result is reviewed, the next PR8.7 commit can safely choose between:

```text
A  repair selector/evidence logic if T0 is not proven

B  integrate proven pre-write Temporary selection,
   explicit conversation_mode governance,
   provenance, and remaining live gates
```

## 12. Architecture-invalidation check

After each characterization step ask:

```text
Can the existing ProductWriteTransport / canonical split safely express Temporary Chat?

Can the write plane prove Temporary selection before mutation?

Can the canonical plane represent the resulting terminal/identity semantics without fabricating durable state?
```

If the answer becomes no because Temporary Chat fundamentally requires a different product-runtime ownership model, mark:

```text
FUNDAMENTAL_BOUNDARY_DISCOVERED
```

and advance PR9.0 rather than forcing Temporary Chat into an invalid abstraction.

## 13. Current PR8.7 state after this commit

```text
Temporary Chat product existence              documented externally
Temporary Chat adapter capability              UNKNOWN
isolated selector characterization primitive   IMPLEMENTED
normal production text-turn path                UNCHANGED
production temporary send                       NOT ENABLED
silent durable fallback                         NOT INTRODUCED
challenge/protection expansion                  NONE
```

The next authoritative input is the live sanitized probe output from the user's real logged-in ChatGPT product session.
