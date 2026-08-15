# PR8.7 Temporary Chat live characterization evidence

_Status: evidence log for PR8.7; production Temporary Chat remains capability-gated_

_Date: 2026-08-15_

This document records the live observations that motivated the transition from a no-write Temporary-mode selector probe to a controlled one-shot write characterization. It is intentionally separate from the production capability declaration.

## 1. Current production status

```text
temporary_chat = UNKNOWN
production conversation_mode="temporary" = NOT ENABLED
ordinary production send path = UNCHANGED
```

All probes in this document are research/diagnostic only.

## 2. Official product expectation

Current OpenAI Temporary Chat documentation states that Temporary Chats:

- start from a new chat through the Temporary control;
- do not appear in normal history;
- do not access or create memories for personalization;
- are not used to improve models;
- may still be retained for up to 30 days for safety purposes.

For PR8.7 the critical persistence invariant is therefore:

```text
TRUE PRODUCT TEMPORARY SEMANTICS
        ->
conversation does not appear in ordinary user history
```

A UI marker containing the word `Temporary` is not equivalent to this persistence invariant.

## 3. Live no-write run A — DOM selected-state attributes

Observed:

```text
control_found                  true
candidate_count                1
selected_before                null
selected_after                 null
mode_selection_proven          false
match_signals                  [aria_label]
conversation_write_observed    false
foreground_activation_observed false
probe_tab_closed               true
```

Conclusion:

- the current web product exposes one unambiguous visible Temporary control;
- clicking that control does not itself cause a conversation POST;
- the isolated inactive probe can close cleanly without foreground activation;
- the control does not expose `aria-pressed`, `aria-checked`, `aria-current`, `data-selected`, or recognized `data-state` values sufficient to prove selected state.

## 4. Live no-write run B — aria-label action semantics

The next characterization attempted to interpret an accessibility label only when it unambiguously described a state-changing action such as `turn on`, `turn off`, `enable`, or `disable`.

Observed again:

```text
match_signals          [aria_label]
selected_before        null
selected_after         null
mode_selection_proven  false
```

Conclusion:

The current Temporary control's aria-label identifies the feature but does not expose usable on/off action semantics. The action-label hypothesis is therefore not accepted as production evidence.

## 5. Live no-write run C — Accessibility Tree

Repository regression state at this stage:

```text
840 passed
```

Observed before activation:

```text
AX candidate_count            1
AX actionable_candidate_count 1
AX roles                      [button]
AX state_signals              []
AX selection_state            null
```

Observed immediately after activation:

```text
AX candidate_count            6
AX actionable_candidate_count 1
AX roles                      [button, inlinetextbox, statictext, tooltip]
AX state_signals              []
AX selection_state            null
```

Conclusion:

The extra AX nodes were consistent with hover/tooltip-related presentation rather than an explicit selected-state signal. `pressed`, `checked`, `selected`, `expanded`, `haspopup`, `disabled`, and `focused` did not provide an authoritative Temporary selection proof.

## 6. Live no-write run D — tooltip-dismissed semantic page notice

The probe then moved the pointer away from the control, waited for transient tooltip UI to disappear, and searched only for bounded page-level semantic markers associated with Temporary/history/memory/training behavior.

Observed:

```text
AX before:
  candidate_count            1
  actionable_candidate_count 1
  roles                      [button]
  state_signals:
    semantic-candidate-count:0
    semantic-title-temporary:false
    semantic-url-temporary:false

AX after:
  candidate_count            1
  actionable_candidate_count 1
  roles                      [button]
  state_signals:
    semantic-candidate-count:0
    semantic-title-temporary:false
    semantic-url-temporary:false

selected_before        null
selected_after         null
mode_selection_proven  false
conversation_write_observed false
foreground_activation_observed false
probe_tab_closed true
```

Conclusion:

After tooltip dismissal, the before/after structural view is effectively identical. The current product does not expose a reliable pre-write Temporary selected-state proof through the bounded DOM, Accessibility Tree, URL/title, or page-level semantic notice channels characterized so far.

## 7. T0 interpretation

The original T0 requirement was:

```text
Temporary selected state can be proven before write
```

The live evidence supports this more precise statement:

```text
PROVEN:
- one unique Temporary control can be located on a fresh new-chat page;
- that control can be activated in an isolated inactive tab;
- activation alone creates no conversation write;
- probe tabs remain isolated, inactive, and disposable.

NOT PROVEN:
- selected-state confirmation before the first conversation write.
```

Do not weaken this negative result into a fabricated selected state.

## 8. Controlled one-shot write boundary

The diagnostic CLI is:

```powershell
python -m chatgpt_web_adapter.temporary_chat_turn_probe \
  --acknowledge-durable-risk \
  --timeout 150
```

Default smoke prompt:

```text
Reply with exactly: SDK_TEMPORARY_CHAT_TURN_OK
```

The acknowledgement is mandatory because pre-write selected state is not observable. If Temporary activation does not take effect before mutation, the experiment can create one ordinary durable smoke conversation.

No automatic retry is permitted.

## 9. Live controlled-write run E — identity/finality success, persistence contradiction

The first controlled write returned:

```text
activation_action                 click_unique_control_without_selected_state_proof
selection_proven_before_write     false
selected_before                   null
selected_after_activation         null
selected_after_turn               true  [old interpretation; repaired below]
post_turn_proof_signals            [semantic:document-title-temporary]
conversation_write_count           1
response_status                    200
response_mime_type                 text/event-stream
final_url_kind                     conversation
url_conversation_id_present        true
foreground_activation_observed     false
probe_tab_closed                   true
```

Returned identity:

```text
conversation_id   6a807935-82b4-83ed-a10e-5231cc2ba458
turn_exchange_id  d5736236-4b89-4e04-8023-551d2137b06d
```

After the disposable browser tab closed, browserless canonical observation succeeded:

```text
status_ok                 true
status                    completed
status_finish_reason      stop
messages_ok               true
message_count             3
user_message_count        1
assistant_message_count   2
observed_model            gpt-5-6-thinking
attach_ok                 true
attach_current_node       present
attach_detected_model     gpt-5-6-thinking
attach_title              present
```

This establishes an important positive result:

```text
A Temporary-candidate turn can use an ordinary conversation_id
and remain canonically readable after the disposable page is gone.
```

Therefore PR8.7 must not assume that product Temporary requires a different backend identity type or a browser-only readback plane.

However the user then manually observed that this same conversation **appeared in ordinary ChatGPT history**.

That contradicts the documented Temporary Chat persistence contract.

Current interpretation:

```text
T1 page-owned one-shot write              PASS
T2 canonical terminal/readback            PASS
T3 identity characterization              PASS
T4 no ordinary-history persistence        FAIL / CONTRADICTED
```

The capability therefore remains:

```text
temporary_chat = UNKNOWN
```

and must not advance to `AVAILABLE`.

## 10. Critical provenance repair — UI marker != selection proof

The old turn probe promoted:

```text
semantic:document-title-temporary
```

into:

```text
selected_after_turn = true
```

Run E proves that this implication is too strong.

A Temporary-looking page title can coexist with persistence behavior that is not Temporary according to the product contract.

PR8.7 now separates:

```text
UI_MODE_MARKER
    document title / URL / semantic notice suggests Temporary

SELECTION_PROOF
    explicit control state evidence, currently unavailable

PERSISTENCE_SEMANTICS
    independent evidence that the conversation is absent from ordinary history
```

The invariant is:

```text
UI_MODE_MARKER != PRODUCT_TEMPORARY_PROOF
```

Accordingly `semantic:document-title-temporary`, `semantic:url-temporary`, and `semantic:product-notice` are diagnostic UI marker signals only. They no longer set `selected=true` and no longer count as selection proof.

## 11. Fresh-root history-presence probe

Manual sidebar observation is already evidence, but PR8.7 should make T4 reproducible without relying on chat titles or human visual matching.

The next no-write diagnostic is:

```powershell
python -m chatgpt_web_adapter.temporary_chat_history_probe \
  6a807935-82b4-83ed-a10e-5231cc2ba458 \
  --timeout 30
```

It performs:

```text
fresh inactive https://chatgpt.com/
        -> wait for fresh page/history surface
        -> inspect only same-origin /c/<id> links
        -> compare exact returned conversation_id
        -> export booleans/counts only
        -> close probe tab
```

It does not export conversation titles, link text, raw DOM, prompt text, or assistant text and performs no chat write.

A result such as:

```text
history_surface_ready      true
history_link_present       true
history_visible_link_present true
```

would independently reproduce the manual T4 failure after a fresh page load.

Absence is weaker evidence than presence because sidebar loading/virtualization can hide entries, so `history_link_present=false` is not by itself sufficient to prove true Temporary semantics.

## 12. What the Run E result changes architecturally

The canonical/read plane should **not** be redesigned merely because Temporary Chat is ephemeral at the product-policy level.

Run E supports this model as a viable hypothesis:

```text
ordinary backend conversation identity
        +
ordinary canonical status/messages/attach
        +
Temporary-specific persistence/personalization policy
```

That is favorable for HDE because a future Temporary call may still use the same canonical observation machinery while differing only in write-mode governance and persistence provenance.

What remains unresolved is the actual activation boundary:

```text
Did our control click fail to activate Temporary before the POST?
Did activation require additional settling/readiness?
Did a UI Temporary marker appear without backend Temporary policy?
Is there another product-state transition that occurs only after mutation?
```

The next experiments should answer those questions without reconstructing or replaying private protected write requests.

## 13. Remaining evidence matrix

```text
T0  unique Temporary control / isolated activation        PARTIAL PASS
T1  one page-owned text turn                              PASS
T2  terminal response/readback                            PASS
T3  identity semantics                                    PASS
T4  absence from ordinary history                         FAIL / CONTRADICTED
T5  no normal durable fallback when activation fails      OPEN
T6  continuation behavior                                 OPEN
T7  requested/observed conversation-mode provenance       OPEN
T8  TEMP -> NORMAL isolation                              OPEN
T9  NORMAL -> TEMP isolation                              OPEN
T10 cold/warm/runtime-tab recreation                      OPEN
T11 capability UNKNOWN -> AVAILABLE                       BLOCKED
```

## 14. Architecture-invalidation check

No fundamental architecture invalidation has been observed.

The existing split can still express the evidence:

```text
browser-owned page = mutation / product-authority plane
browserless canonical client = identity/finality/read plane
product persistence semantics = separate evidence dimension
HDE/public runtime = still not exposed to Temporary-specific production policy
```

The blocker is not canonical readability. The blocker is proving that the requested product mode actually receives Temporary persistence/personalization semantics before we expose it as a production capability.
