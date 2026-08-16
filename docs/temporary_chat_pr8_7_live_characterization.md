# PR8.7 Temporary Chat live characterization evidence

_Status: evidence log for PR8.7; production Temporary Chat remains capability-gated_

_Date: 2026-08-16_

This document records the live evidence used to characterize ChatGPT Temporary Chat for `chatgpt-web-adapter`. It is deliberately separate from the production capability declaration. The evidence below describes what the product was observed to do; it does not by itself enable production `conversation_mode="temporary"`.

## 1. Current production status

```text
temporary_chat = UNKNOWN
production conversation_mode="temporary" = NOT ENABLED
ordinary production send path = UNCHANGED
```

All Temporary probes in this document remain research/diagnostic surfaces.

## 2. Correct semantic vocabulary

PR8.7 now has enough evidence to distinguish several identities and lifetimes that must not be collapsed:

```text
TRUE TEMPORARY SOURCE SESSION
    The live ChatGPT page entered at /?temporary-chat=true.

TEMPORARY PRODUCT CONVERSATION ID
    A stable ID emitted by the product write path and reused by multiple
    live Temporary turns. Current probe field names may still call this
    ephemeral_backend_conversation_id for compatibility.

LIVE TEMPORARY LIFECYCLE
    The interval during which the original Temporary source session remains
    live and accepts continued page-owned writes.

POST-CLOSE PRODUCT-ROUTE RECOVERY
    The observed ability of /c/<temporary-product-conversation-id> to hydrate
    previously completed Temporary turns after the original source closes.

ORDINARY HISTORY ENUMERATION
    Presence of an exact /c/<id> entry in the normal ChatGPT sidebar/history.

ORDINARY CANONICAL CONVERSATION READ
    GET /backend-api/conversation/<id> through the existing browserless
    canonical observation plane.
```

Critical invariants:

```text
TEMPORARY PRODUCT CONVERSATION ID
    != ordinary canonical conversation contract

HISTORY ENUMERATION
    != product-route recoverability
    != canonical direct-ID readability
    != server retention

POST-CLOSE READ/RECOVERY EVIDENCE
    != post-close write authority
```

A `404` from the ordinary canonical conversation endpoint must not be interpreted as proof that no product-side Temporary state exists.

## 3. Earlier automated activation result is an ordinary durable control

The earlier automated experiment that attempted to click a Temporary-looking control before writing produced an ordinary history-visible durable chat. It remains useful only as an ordinary-chat control.

Therefore the following are withdrawn as Temporary evidence:

```text
automated Temporary activation is proven
Temporary supports ordinary canonical get_status/get_messages
Temporary supports attach_conversation
Temporary has ordinary durable-chat persistence
```

The authoritative Temporary evidence below comes from a human-established true Temporary source page at:

```text
https://chatgpt.com/?temporary-chat=true
```

The adapter did not click or infer the Temporary control for those ground-truth writes.

## 4. True Temporary single-turn ground truth

A manually prepared true Temporary source page accepted one page-owned text turn.

Observed identity:

```text
temporary product conversation id:
6a818eb9-7e88-83ed-9218-4501375b2715
```

Important fields:

```text
same_source_tab                         true
initial_url_temporary_query_true        true
final_url_temporary_query_true          true
initial_url_conversation_id_present     false
url_conversation_id_present             false
conversation_write_count                1
response_status                         200
response_mime_type                      text/event-stream
conversation_turn_count_before          0
conversation_turn_count_after           2
turn_count_growth                       2
user_message_visible_after_turn         true
assistant_message_visible_after_turn    true
turn_surface_selector_kind              conversation-testid
```

The exact expected-assistant-text matcher returned a false negative even though the assistant reply was later visually confirmed. Exact-text matching is therefore a diagnostic only and is not part of the authoritative visible-turn gate.

Conclusion:

```text
T2 true Temporary page-owned visible text turn = PASS
```

## 5. Stable Temporary conversation identity exists

The true Temporary write emitted a conversation-shaped identifier while the visible product route remained the Temporary root page rather than `/c/<id>`.

This ID is not merely a one-shot request token: a later fresh live Temporary experiment reused the same ID across two sequential turns.

Current terminology:

```text
temporary_product_conversation_id
```

Probe field names that still use `ephemeral_backend_conversation_id` are retained only for compatibility and should not be read as a claim that the ID has ordinary canonical-conversation semantics.

Conclusion:

```text
T3 stable Temporary product conversation identity = PROVEN
```

## 6. Ordinary history is absent while the true Temporary session is live

For the first true Temporary ID, a settled fresh-root history probe observed:

```text
history_evidence_status     STABLE_ABSENT
history_absence_proven      true
seen_sample_count           0
absent_sample_count         31
settle_completed            true
history_surface_ready       true
conversation_link_count     37
visible_conversation_link_count 37
```

The probe searches exact `/c/<id>` anchors; it does not navigate to the target ID.

Conclusion:

```text
T5 exact Temporary ID absent from settled ordinary history = PASS
```

This proves exact-ID non-enumeration in the observed history surface. It does not prove that no alternate internal representation exists.

## 7. Ordinary canonical direct-ID read returns 404 while the source is live

While the original true Temporary source tab was still open:

```text
GET /backend-api/conversation/6a818eb9-7e88-83ed-9218-4501375b2715
-> 404
```

Probe result:

```text
canonical_payload_read_calls          1
canonical_read_succeeded              false
canonical_readability_status          NOT_FOUND
http_status                            404
browser_navigation_performed          false
product_route_open_attempted          false
attach_performed                      false
write_performed                       false
```

Conclusion:

```text
T4 ordinary canonical direct-ID readability while live = NOT_FOUND / 404
```

This is a statement about the existing canonical conversation endpoint, not about all possible product/backend storage.

## 8. Canonical 404 read does not materialize ordinary history

A settled history probe run after the T4 canonical read again returned:

```text
history_evidence_status = STABLE_ABSENT
history_absence_proven  = true
seen_sample_count       = 0
absent_sample_count     = 31
```

Conclusion:

```text
T6 canonical-read exact-ID ordinary-history materialization = NONE OBSERVED / PASS
```

## 9. Ordinary canonical direct-ID read remains 404 after source close

After closing the original true Temporary source tab, the same one-read probe returned:

```text
source_temporary_tab_state    CLOSED
canonical_readability_status  NOT_FOUND
http_status                    404
canonical_payload_read_calls   1
```

Conclusion:

```text
T7a ordinary canonical read after source close = NOT_FOUND / 404
```

Closing the source did not promote this ID into the ordinary canonical conversation endpoint.

## 10. Direct product route can stably recover a closed Temporary conversation

A dedicated read-only route-reopen probe opened:

```text
https://chatgpt.com/c/6a818eb9-7e88-83ed-9218-4501375b2715
```

after the original Temporary source had closed.

Observed:

```text
target_route_observed                         true
target_route_sample_count                     54
root_route_observed                           false
redirect_away_from_target_observed            false
final_url_kind                                exact_target
final_url_conversation_id_matches_target      true
visible_turn_surface_observed                 true
max_visible_turn_count                        2
final_visible_turn_count                      2
recovered_sample_count                        45
stable_recovered                              true
recovery_evidence_status                      STABLE_RECOVERED
conversation_write_count                      0
canonical_http_read_performed                 false
```

Conclusion:

```text
T7b post-close product-route recovery = STABLE_RECOVERED / PASS
```

This proves stable product-route recoverability of completed Temporary turns. It does not prove ordinary history persistence, canonical API readability, or continued write authority.

## 11. Direct-route recovery still does not materialize ordinary history

After a successful direct `/c/<id>` recovery, the ordinary history probe again returned:

```text
history_evidence_status = STABLE_ABSENT
history_absence_proven  = true
seen_sample_count       = 0
absent_sample_count     = 31
```

Conclusion:

```text
T7c ordinary-history materialization after direct reopen = NONE OBSERVED / PASS
```

Observed Temporary state is therefore:

```text
direct-addressable
+
product-route recoverable
+
ordinary-history undiscoverable
+
ordinary-canonical-API unreadable
```

## 12. Post-close continuation is rejected

The controlled continuation probe attempted exactly one page-owned continuation write to the recovered Temporary product conversation after the original source lifecycle had ended.

Observed result:

```text
CHATGPT_TURN_HTTP_STATUS:404
```

The user also observed one manual case where the new user message appeared in the recovered UI without an assistant answer, then disappeared after page reload. That observation is consistent with an optimistic/local UI append, but the exact internal mechanism is not proven.

Authoritative conclusion:

```text
post-close write persistence = NOT PROVEN
post-close controlled continuation = REJECTED / HTTP 404
```

The product-route-readable post-close state must not be promoted into a writable continuation contract.

## 13. Live Temporary multi-turn continuation is proven

A new true Temporary source page was opened manually and kept alive for two sequential controlled writes.

Temporary product conversation ID:

```text
6a81a6ef-78a4-83eb-8b58-cf4d683bec56
```

### Turn 1

```text
source_tab_id                     1949459774
conversation_id                   6a81a6ef-78a4-83eb-8b58-cf4d683bec56
conversation_write_count          1
response_status                    200
response_mime_type                 text/event-stream
conversation_turn_count_before     0
conversation_turn_count_after      2
turn_count_growth                  2
initial_url_temporary_query_true   true
final_url_temporary_query_true     true
visible_turn_ground_truth_proven   true
```

### Turn 2, without closing or reloading the source

```text
source_tab_id                     1949459774
conversation_id                   6a81a6ef-78a4-83eb-8b58-cf4d683bec56
conversation_write_count          1
response_status                    200
response_mime_type                 text/event-stream
conversation_turn_count_before     2
conversation_turn_count_after      4
turn_count_growth                  2
initial_url_temporary_query_true   true
final_url_temporary_query_true     true
visible_turn_ground_truth_proven   true
```

The source tab and Temporary product conversation ID were identical across both runs; `turn_exchange_id` changed as expected for a new turn.

Conclusion:

```text
LIVE Temporary session
    -> normal multi-turn conversation semantics = PROVEN
    -> same Temporary product conversation identity = PROVEN
    -> 0 -> 2 -> 4 visible-turn growth = PROVEN
    -> two sequential writes = HTTP 200 / PASS
```

This is the decisive evidence that Temporary Chat is not a one-shot request primitive.

## 14. A live two-turn Temporary conversation still remains absent from ordinary history

While the two-turn Temporary source was still live, exact-ID history enumeration returned:

```text
history_evidence_status          STABLE_ABSENT
history_absence_proven           true
seen_sample_count                0
absent_sample_count              31
settle_completed                 true
history_surface_ready            true
conversation_link_count          37
visible_conversation_link_count  37
```

Conclusion:

```text
live writable multi-turn Temporary
    != ordinary history-visible durable conversation
```

## 15. All four completed turns survive source close as a stable product-route recovery

The same two-turn Temporary source was then closed. A read-only direct-route reopen probe for the same ID returned:

```text
target_route_observed                         true
target_route_sample_count                     54
root_route_observed                           false
redirect_away_from_target_observed            false
final_url_kind                                exact_target
final_url_conversation_id_matches_target      true
visible_turn_surface_observed                 true
max_visible_turn_count                        4
final_visible_turn_count                      4
recovered_sample_count                        48
stable_recovered                              true
recovery_evidence_status                      STABLE_RECOVERED
conversation_write_count                      0
canonical_http_read_performed                 false
```

The user visually confirmed the two sequential user/assistant exchanges.

Conclusion:

```text
LIVE:
    0 -> 2 -> 4 visible turns
    writable
    HTTP 200

SOURCE CLOSE

POST-CLOSE:
    same exact product route
    same four completed turns
    STABLE_RECOVERED
    no write performed by recovery probe
```

This establishes preservation of completed multi-turn Temporary state across source close in the product route.

## 16. Current lifecycle model supported by evidence

The strongest evidence-backed model is:

```text
                TRUE TEMPORARY CONVERSATION

                   LIVE LIFECYCLE
                         |
              +----------+----------+
              |                     |
           readable               writable
              YES                   YES
              |                     |
        page-owned turns       sequential turns
          0 -> 2 -> 4          HTTP 200
              |                     |
              +----------+----------+
                         |
                    SOURCE CLOSE
                         |
                         v
                 POST-CLOSE STATE
                         |
              +----------+----------+
              |                     |
      product-route recovery      writable
              YES                   NO
              |                     |
         old completed          controlled write
         turns hydrate            HTTP 404
         STABLE_RECOVERED
```

Orthogonal observations:

```text
ordinary sidebar/history exact ID = STABLE_ABSENT
ordinary canonical GET by same ID = 404 while live
ordinary canonical GET by same ID = 404 after close
```

Therefore:

```text
identity exists
!= ordinary canonical readability
!= ordinary history discoverability
!= post-close write authority
```

## 17. Corrected PR8.7 evidence matrix

```text
T0  automatic unique-control discovery / safe click          PARTIAL PASS
T1  automated Temporary product-mode activation              NOT PROVEN

T2  true Temporary page-owned visible text turn              PASS
T3  stable Temporary product conversation identity           PROVEN

T4  ordinary canonical direct-ID read while source live      NOT_FOUND / 404
T5  exact ID in settled ordinary history while live          STABLE_ABSENT / PASS
T6  canonical-read history-materialization side effect       NONE OBSERVED / PASS

T7a ordinary canonical read after source close               NOT_FOUND / 404
T7b direct product-route recovery after source close         STABLE_RECOVERED / PASS
T7c history materialization after direct reopen              NONE OBSERVED / PASS
T7d post-close controlled continuation                       REJECTED / HTTP 404

T7-live
    two sequential live Temporary turns                      PASS
    same product conversation ID                             PROVEN
    visible-turn growth 0 -> 2 -> 4                          PROVEN
    live two-turn ordinary-history visibility                STABLE_ABSENT
    post-close recovery of all four turns                    STABLE_RECOVERED

T8  no normal durable fallback in production path            OPEN
T9  requested/observed conversation-mode provenance          OPEN
T10 TEMP -> NORMAL isolation                                  OPEN
T11 NORMAL -> TEMP isolation                                  OPEN
T12 lifecycle/cold-warm/runtime-tab recreation governance    OPEN
T13 capability UNKNOWN -> AVAILABLE                           BLOCKED
```

Production capability remains blocked on T8-T12 even though the core Temporary lifecycle is now characterized.

## 18. Claims PR8.7 must not make

Do not claim:

```text
Temporary is an ordinary durable chat.
Temporary appears in ordinary history.
Temporary is readable through the existing canonical conversation endpoint.
A Temporary product conversation ID is sufficient authority to continue after close.
attach_conversation() is supported for Temporary.
Direct /c/<id> recovery is a production continuation contract.
HTTP 404 means no Temporary product state exists anywhere.
Automatic UI activation is trustworthy.
```

Also do not infer that post-close route recovery has a guaranteed retention duration. The experiments prove observed recovery, not a duration SLA.

## 19. Production consequences

The live evidence now constrains the target production semantics:

```text
1. Explicit Temporary selection must fail closed.
2. A live Temporary conversation is multi-turn, not one-shot.
3. Continuation must be bound to a live Temporary lifecycle/session authority,
   not merely to a remembered conversation ID.
4. Page-owned observation/finality is authoritative for live Temporary writes;
   ordinary canonical GET cannot be required.
5. Temporary must not promise ordinary history enumeration.
6. Temporary must not promise attach_conversation().
7. Source-lifecycle termination ends production write authority.
8. Post-close /c/<id> recovery may remain diagnostic evidence, but must not be
   advertised as a durable production reopen/continue contract.
9. No Temporary failure may silently fall back to a normal durable chat.
10. requested_mode and observed_mode provenance must remain explicit.
```

The companion design document `temporary_chat_pr8_7.md` defines the resulting target production contract.

## 20. Current capability decision

The evidence is now sufficient to characterize the core lifecycle, but not yet sufficient to graduate the public capability.

```text
temporary_chat = UNKNOWN
production conversation_mode="temporary" = NOT ENABLED
```

Next gates:

```text
T8  production no-durable-fallback governance
T9  requested/observed mode provenance
T10 TEMP -> NORMAL isolation
T11 NORMAL -> TEMP isolation
T12 lifecycle / cold-warm / runtime-tab recreation governance
```

Only after those gates are reviewed should PR8.7 consider:

```text
temporary_chat: UNKNOWN -> AVAILABLE
```
