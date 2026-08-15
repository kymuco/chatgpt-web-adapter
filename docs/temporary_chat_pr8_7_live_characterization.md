# PR8.7 Temporary Chat live characterization evidence

_Status: evidence log for PR8.7; production Temporary Chat remains capability-gated_

_Date: 2026-08-15_

This document records the live observations used to characterize Temporary Chat before exposing it through the production product runtime. It is intentionally separate from the production capability declaration.

## 1. Current production status

```text
temporary_chat = UNKNOWN
production conversation_mode="temporary" = NOT ENABLED
ordinary production send path = UNCHANGED
```

All probes in this document are research/diagnostic only.

## 2. Official product expectation and the three distinct persistence questions

Current OpenAI Temporary Chat documentation states that Temporary Chats:

- start from a new chat through the Temporary control;
- do not appear in normal user history;
- do not access or create memories for personalization;
- are not used to improve models;
- may still be retained by OpenAI for up to 30 days for safety purposes.

That means PR8.7 must keep three questions separate:

```text
A. USER-HISTORY ENUMERATION
   Does the conversation appear in the normal ChatGPT history/sidebar?

B. DIRECT-ID READABILITY
   If the exact conversation_id is already known, can an authenticated
   canonical read still retrieve the conversation after the page closes?

C. SERVER RETENTION
   Does OpenAI still retain a copy internally for some bounded period?
```

The critical invariant is:

```text
HISTORY_ENUMERATION != DIRECT_ID_READABILITY != SERVER_RETENTION
```

A Temporary Chat may be absent from normal history while a retained copy still exists for up to 30 days. Therefore successful canonical readback by a known id does not by itself contradict Temporary semantics and must not be described as "materializing" a chat back into user history.

For HDE the desired one-shot lifecycle is consequently:

```text
send
-> observe/stream response
-> prove canonical finality
-> verify no stable user-history persistence
-> release browser authority
```

Long-term recoverability after that point is not required for the one-shot Temporary use case.

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

The probe moved the pointer away from the control, waited for transient tooltip UI to disappear, and searched only for bounded page-level semantic markers associated with Temporary/history/memory/training behavior.

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

## 9. Live controlled-write run E — identity/finality success

The first controlled write returned:

```text
activation_action                 click_unique_control_without_selected_state_proof
selection_proven_before_write     false
selected_before                   null
selected_after_activation         null
selected_after_turn               true  [old interpretation; repaired below]
post_turn_proof_signals           [semantic:document-title-temporary]
conversation_write_count          1
response_status                   200
response_mime_type                text/event-stream
final_url_kind                    conversation
url_conversation_id_present       true
foreground_activation_observed    false
probe_tab_closed                  true
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
A Temporary-candidate turn can use an ordinary backend conversation identity
and browserless canonical status/messages/attach can remain readable after the
disposable page is gone.
```

This is compatible with Temporary semantics because official retention allows a copy to remain on OpenAI systems for a bounded period. Direct-id readability must not be equated with ordinary user-history persistence.

## 10. Critical provenance repair — UI marker != selection proof

The old turn probe promoted:

```text
semantic:document-title-temporary
```

into:

```text
selected_after_turn = true
```

That implication is too strong.

PR8.7 now separates:

```text
UI_MODE_MARKER
    document title / URL / semantic notice suggests Temporary

SELECTION_PROOF
    explicit control state evidence, currently unavailable

HISTORY_ENUMERATION
    whether the conversation is stably listed in normal user history

DIRECT_ID_READABILITY
    whether a known id can still be read through canonical surfaces

SERVER_RETENTION
    whether OpenAI still retains a copy internally
```

The invariants are:

```text
UI_MODE_MARKER != PRODUCT_TEMPORARY_PROOF
HISTORY_ENUMERATION != DIRECT_ID_READABILITY
```

Accordingly `semantic:document-title-temporary`, `semantic:url-temporary`, and `semantic:product-notice` are diagnostic UI marker signals only. They no longer set `selected=true` and no longer count as selection proof.

## 11. Live history observation F — early exact-link presence was not a persistence proof

A first fresh-root history probe for the Run E conversation returned:

```text
probe_context                 fresh_root_history_presence
history_link_present          true
history_visible_link_present  true
conversation_link_count       37
history_surface_ready         true
foreground_activation         false
probe_tab_closed              true
elapsed_ms                    2291
```

The user then reported an important manual observation: the Temporary conversation could no longer be found on the site.

This changes the interpretation of the first history probe. The probe stopped immediately after the first exact-link match, so it only established:

```text
an exact /c/<id> anchor was visible during early root-page loading/hydration
```

It did **not** establish:

```text
the conversation remained stably present in normal history after synchronization
```

Therefore the previous interpretation:

```text
T4 no ordinary-history persistence = FAIL / CONTRADICTED
```

is withdrawn.

The current interpretation is:

```text
T1 page-owned one-shot write        PASS
T2 canonical terminal/readback      PASS
T3 identity characterization        PASS
T4 user-history persistence         TRANSIENT / UNRESOLVED
```

The capability remains:

```text
temporary_chat = UNKNOWN
```

because stable absence still needs evidence, but the current evidence no longer supports claiming a durable-history failure.

## 12. History settling probe

The history diagnostic now observes the exact conversation link across a bounded settling window instead of exiting on first sight.

Command:

```powershell
python -m chatgpt_web_adapter.temporary_chat_history_probe \
  6a807935-82b4-83ed-a10e-5231cc2ba458 \
  --timeout 30
```

It reports:

```text
history_link_present
history_visible_link_present
final_history_link_present
final_history_visible_link_present
stable_history_presence
transient_history_presence
disappeared_after_seen
first_seen_ms
last_seen_ms
seen_sample_count
absent_sample_count
settle_window_ms
observation_window_ms
```

Interpretation:

```text
stable_history_presence=true
    -> strong evidence of ordinary user-history persistence

transient_history_presence=true
and final_history_visible_link_present=false
    -> the link appeared during hydration but disappeared after synchronization

history_link_present=false
    -> absence observation only; still weaker than a positive stable-presence result
```

The probe remains no-write and does not export conversation titles, link text, raw DOM, prompt text, or assistant text.

## 13. Canonical-read materialization hypothesis

Run E performed browserless `get_status`, `get_messages`, and `attach_conversation` immediately after closing the disposable Temporary-candidate page and before the first history probe.

Therefore one additional confound remains:

```text
Did canonical observation merely read a retained Temporary conversation,
or can one of those read/attach operations influence normal history visibility?
```

PR8.7 must not assume either answer.

The clean experiment is:

```text
new Temporary-candidate one-shot turn
        -> close page
        -> DO NOT perform canonical read yet
        -> run settled fresh-root history observation
        -> then perform canonical status/messages/attach
        -> run settled fresh-root history observation again
```

This will separate:

```text
product write persistence behavior
from
possible read/attach materialization side effects
```

No private write-body reconstruction is required.

## 14. What Run E changes architecturally

The canonical/read plane should not be redesigned merely because Temporary Chat is ephemeral at the user-history policy level.

Run E supports this model as a viable hypothesis:

```text
ordinary backend conversation identity
        +
ordinary canonical status/messages/attach
        +
Temporary-specific user-history / personalization policy
```

That is favorable for HDE. A future Temporary call may be able to use the same canonical finality machinery while differing in conversation-mode governance, history behavior, memory behavior, and lifecycle/TTL.

For the intended HDE one-shot use case, the important requirement is not that the backend erase the object immediately after page close. The important requirement is that the request does not clutter ordinary ChatGPT history or participate in personalization memory, while the adapter can still obtain an authoritative response and reconcile the turn.

## 15. Remaining evidence matrix

```text
T0  unique Temporary control / isolated activation        PARTIAL PASS
T1  one page-owned text turn                              PASS
T2  terminal response/readback                            PASS
T3  identity semantics                                    PASS
T4  absence from stable ordinary history                  TRANSIENT / UNRESOLVED
T5  canonical-read materialization side effect            OPEN
T6  no normal durable fallback when activation fails      OPEN
T7  continuation behavior                                 OPEN
T8  requested/observed conversation-mode provenance       OPEN
T9  TEMP -> NORMAL isolation                              OPEN
T10 NORMAL -> TEMP isolation                              OPEN
T11 cold/warm/runtime-tab recreation                      OPEN
T12 capability UNKNOWN -> AVAILABLE                       BLOCKED
```

## 16. Architecture-invalidation check

No fundamental architecture invalidation has been observed.

The existing split can still express the evidence:

```text
browser-owned page = mutation / product-authority plane
browserless canonical client = identity/finality/read plane
user-history persistence = separate product-policy evidence dimension
server retention = separate from user-history visibility
HDE/public runtime = still not exposed to Temporary-specific production policy
```

The blocker is no longer "Temporary must have a different identity" and it is not currently proven to be "Temporary persisted durably in history" either. The blocker is proving the actual product-mode semantics across write, stable history visibility, canonical readback, and personalization boundaries before exposing Temporary as a production capability.
