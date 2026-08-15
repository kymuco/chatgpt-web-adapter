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

## 2. Product semantics and three distinct persistence questions

The intended Temporary product semantics require PR8.7 to keep three different questions separate:

```text
A. USER-HISTORY ENUMERATION
   Does the conversation appear in normal ChatGPT history/sidebar?

B. DIRECT-ID READABILITY
   If the exact conversation_id is already known, can an authenticated
   canonical read retrieve the conversation while or after the page exists?

C. SERVER RETENTION
   Does the service retain a copy internally for some bounded period even
   though it is absent from normal history?
```

Critical invariant:

```text
HISTORY_ENUMERATION != DIRECT_ID_READABILITY != SERVER_RETENTION
```

A known-id read must never be interpreted as equivalent to ordinary sidebar persistence. Conversely, absence from sidebar does not by itself prove that the backend object has ceased to exist.

For the HDE one-shot use case the desired lifecycle is:

```text
send
-> observe/stream response
-> prove finality
-> verify no stable user-history persistence
-> release browser authority
```

Long-term recoverability after that point is not required.

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

- one unambiguous visible Temporary control can be located on a fresh page;
- clicking it alone causes no conversation POST;
- the isolated inactive probe does not foreground and closes cleanly;
- the control exposes no usable DOM selected-state attribute through the characterized set.

## 4. Live no-write run B — aria-label action semantics

The next characterization tested whether the accessibility label itself exposed unambiguous on/off action semantics.

Observed:

```text
match_signals          [aria_label]
selected_before        null
selected_after         null
mode_selection_proven  false
```

Conclusion:

The label identifies the feature but does not provide accepted selected-state evidence.

## 5. Live no-write run C — Accessibility Tree

Repository state at this stage:

```text
840 passed
```

Observed before activation:

```text
AX candidate_count             1
AX actionable_candidate_count  1
AX roles                       [button]
AX state_signals               []
AX selection_state             null
```

Immediately after activation:

```text
AX candidate_count             6
AX actionable_candidate_count  1
AX roles                       [button, inlinetextbox, statictext, tooltip]
AX state_signals               []
AX selection_state             null
```

Conclusion:

The additional AX nodes were presentation/tooltip-related. `pressed`, `checked`, `selected`, `expanded`, `haspopup`, `disabled`, and `focused` did not produce authoritative Temporary selection evidence.

## 6. Live no-write run D — tooltip-dismissed semantic page state

After moving the pointer away and waiting for transient tooltip UI to disappear, the structural before/after views were effectively identical:

```text
semantic-candidate-count:0
semantic-title-temporary:false
semantic-url-temporary:false
```

before and after activation.

Therefore pre-write Temporary selection is currently:

```text
PROVEN:
- unique control discovery;
- isolated activation;
- zero write side effect from the activation itself;
- no foreground disturbance.

NOT PROVEN:
- selected-state confirmation before the first write.
```

Do not weaken this negative result into fabricated state.

## 7. Automated controlled-write run E — RECLASSIFIED AS ORDINARY DURABLE CONTROL

An automated diagnostic then:

```text
fresh isolated new-chat page
-> locate unique Temporary control
-> click it without selected-state proof
-> immediately submit one smoke turn
```

It returned:

```text
activation_action                 click_unique_control_without_selected_state_proof
selection_proven_before_write     false
selected_before                   null
selected_after_activation         null
conversation_write_count          1
response_status                   200
response_mime_type                text/event-stream
final_url_kind                    conversation
url_conversation_id_present       true
foreground_activation_observed    false
probe_tab_closed                  true
```

Identity:

```text
conversation_id   6a807935-82b4-83ed-a10e-5231cc2ba458
turn_exchange_id  d5736236-4b89-4e04-8023-551d2137b06d
```

A post-turn UI marker was observed:

```text
semantic:document-title-temporary
```

The old probe incorrectly promoted that UI marker into `selected_after_turn=true`. That interpretation has been repaired.

Most importantly, the user confirmed that this conversation appeared in the ordinary ChatGPT history list. Therefore Run E is now classified as:

```text
ORDINARY DURABLE CONTROL
accidentally produced by automated Temporary-candidate activation
```

It is **not** a true Temporary Chat ground-truth run.

### Evidence that must be withdrawn

The following Run E observations are valid facts about that ordinary control:

```text
get_status(id)       succeeded
get_messages(id)     succeeded
attach_conversation  succeeded
```

But they MUST NOT be used to claim any of the following about Temporary Chat:

```text
"Temporary uses an ordinary backend conversation identity"
"Temporary is canonically readable after page close"
"Temporary supports attach_conversation"
"Temporary survives browser closure in the canonical plane"
```

Those questions are **OPEN again**.

Run E remains useful only as an ordinary-chat baseline showing that the diagnostic write machinery and canonical observation machinery work when the resulting conversation is durable.

## 8. Provenance invariant — UI marker is not product-mode proof

PR8.7 now separates:

```text
UI_MODE_MARKER
    title / URL / semantic notice suggests Temporary presentation

SELECTION_PROOF
    explicit selected-state evidence for the product control

HISTORY_ENUMERATION
    whether the chat is stably listed to the user

DIRECT_ID_READABILITY
    whether a known id can be read by canonical surfaces

SERVER_RETENTION
    whether a backend copy continues to exist
```

Invariants:

```text
UI_MODE_MARKER != PRODUCT_TEMPORARY_PROOF
HISTORY_ENUMERATION != DIRECT_ID_READABILITY
```

`semantic:document-title-temporary`, `semantic:url-temporary`, and `semantic:product-notice` are diagnostic UI markers only. They cannot independently set `selected=true` or establish Temporary semantics.

## 9. History probe F — ordinary-control observation only

A fresh-root history probe for the Run E ordinary-control ID initially returned:

```text
history_link_present          true
history_visible_link_present  true
conversation_link_count       37
history_surface_ready         true
elapsed_ms                    2291
```

The probe was subsequently strengthened with a settling window to distinguish an early hydrated link from stable history presence.

However, because Run E is now known to be an ordinary durable chat, **all history measurements for this ID are ordinary-control evidence only**. They do not characterize true Temporary history behavior.

The generic history settling diagnostic remains useful for a future true Temporary ID. It reports:

```text
stable_history_presence
transient_history_presence
disappeared_after_seen
final_history_visible_link_present
first_seen_ms
last_seen_ms
seen_sample_count
absent_sample_count
```

## 10. Why true Temporary ground truth must now be human-established

The automated activation path created an ordinary durable chat while leaving a Temporary-looking UI marker. Because pre-write selected state is not observable through our characterized DOM/AX channels, another automated `click -> write -> infer mode` experiment would be circular.

The next live experiment therefore uses an external ground truth:

```text
HUMAN OPERATOR
    manually enables Temporary Chat in the visible product UI
    visually confirms the page is in Temporary mode

ADAPTER
    does NOT click the Temporary control
    does NOT infer selected state from CSS/title
    writes exactly one smoke turn into that already prepared page
```

This is the first experiment whose Temporary classification does not depend on the adapter's own unproven activation inference.

## 11. Manual Temporary ground-truth probe

New diagnostic:

```powershell
python -m chatgpt_web_adapter.temporary_chat_manual_ground_truth_probe \
  --manual-temporary-confirmed \
  --timeout 150
```

Preparation is intentionally manual:

```text
1. Open a fresh ChatGPT new-chat page in Chrome.
2. Manually click the Temporary control.
3. Visually confirm that ChatGPT itself shows Temporary mode.
4. Leave that exact fresh ChatGPT tab selected/active.
5. Run the CLI above from the terminal.
```

The extension then:

```text
uses the already selected ChatGPT tab
-> verifies it is still a fresh root new-chat page
-> DOES NOT click Temporary
-> writes exactly one smoke turn
-> observes exactly one conversation POST
-> captures bounded identity / response metadata
-> waits for page-owned completion
-> detaches debugger
-> leaves the source tab OPEN
```

It deliberately performs **no canonical read** and **no history probe** itself.

Default smoke text:

```text
Reply with exactly: SDK_TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_OK
```

## 12. Correct experiment order for a true Temporary conversation

If the manual-ground-truth run returns a `conversation_id`, characterization must happen in this order:

```text
A. TRUE TEMPORARY TAB STILL OPEN
   human confirms it is still Temporary
   record returned conversation_id

B. BEFORE ANY CANONICAL READ
   run settled fresh-root history probe for that id
   -> does it appear in normal history?

C. WHILE TRUE TEMPORARY TAB IS STILL OPEN
   perform canonical get_status/get_messages/attach characterization
   -> can a known Temporary id be read at all?

D. HISTORY AGAIN
   run settled history probe again
   -> did canonical read affect sidebar visibility?

E. CLOSE THE TRUE TEMPORARY SOURCE TAB

F. CANONICAL READ AFTER CLOSE
   repeat status/messages/attach
   -> does known-id readability survive browser-page disposal?

G. HISTORY AGAIN
   verify that post-close canonical reads did not create ordinary history persistence
```

This sequence separates three questions that Run E accidentally mixed together:

```text
true product mode
canonical/direct-id readability
user-history persistence
```

## 13. Corrected evidence matrix

```text
T0  automatic unique-control discovery / safe click        PARTIAL PASS
T1  automated Temporary product-mode activation            NOT PROVEN
T2  true Temporary page-owned text turn                    OPEN
T3  true Temporary conversation identity                   OPEN
T4  true Temporary canonical read while page open          OPEN
T5  true Temporary absence from stable ordinary history    OPEN
T6  canonical-read history-materialization side effect     OPEN
T7  true Temporary canonical read after page close         OPEN
T8  no normal durable fallback in production path          OPEN
T9  requested/observed conversation-mode provenance        OPEN
T10 TEMP -> NORMAL isolation                                OPEN
T11 NORMAL -> TEMP isolation                                OPEN
T12 cold/warm/runtime-tab recreation                        OPEN
T13 capability UNKNOWN -> AVAILABLE                         BLOCKED
```

Run E is explicitly outside this matrix except as an ordinary durable control/baseline.

## 14. Architecture-invalidation check

No fundamental architecture invalidation is established yet.

What is known:

```text
browser-owned ordinary write machinery works
canonical ordinary-chat observation works
automatic Temporary activation is not yet trustworthy
true Temporary identity/readback semantics remain unknown
```

Therefore PR8.7 must not redesign the canonical plane around assumptions drawn from Run E, and it must not expose production Temporary mode yet.

Current capability remains:

```text
temporary_chat = UNKNOWN
```

The next decisive evidence must come from a **manual Temporary ground truth** conversation, not from the ordinary-control ID generated by Run E.
