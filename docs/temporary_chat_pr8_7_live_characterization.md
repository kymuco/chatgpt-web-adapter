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

The controlled write probe added after these observations is research/diagnostic only.

## 2. Live no-write run A — DOM selected-state attributes

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

## 3. Live no-write run B — aria-label action semantics

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

## 4. Live no-write run C — Accessibility Tree

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

## 5. Live no-write run D — tooltip-dismissed semantic page notice

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

## 6. T0 interpretation

The original T0 requirement was:

```text
Temporary selected state can be proven before write
```

The live evidence now supports a more precise statement:

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

## 7. Why the next experiment is a controlled write

Continuing to add CSS/icon/DOM heuristics would increase fragility without increasing semantic confidence.

The next experiment therefore asks a different question:

> After activating the unique Temporary control on a fresh isolated page, what product identity, URL, response, and canonical-readback behavior is actually produced by one real turn?

This is characterization, not production enablement.

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

The explicit acknowledgement is mandatory because pre-write selected state is not observable. If Temporary activation did not take effect, the experiment may create one ordinary durable smoke conversation.

The experiment uses:

```text
dedicated inactive new-chat tab
        -> locate exactly one Temporary control
        -> activate it once
        -> send exactly one smoke turn
        -> observe exactly one conversation POST
        -> wait for page-owned completion
        -> collect safe identity / HTTP / final-URL metadata
        -> detach debugger
        -> close disposable tab
        -> canonical get_status / get_messages / attach by returned identity
```

No automatic retry is permitted.

## 9. Safe output contract

Browser-side output may include:

```text
conversation_id or null
turn_exchange_id or null
response status / mime type
final URL category, not raw arbitrary URL
whether URL contains a conversation id
submit strategy / timing
selection proof signals if any appear after activation or after the turn
foreground activation observation
probe-tab closure
```

Canonical post-close output may include:

```text
status success/failure
status category / observed finish_reason
message count
user / assistant message counts
observed model identifiers
attach success/failure
current-node presence
model presence
title presence
failure class names
```

The diagnostic does not export:

```text
cookies
Authorization headers
protection credentials
request bodies
raw SSE bodies
raw DOM
raw AX tree
assistant response text
canonical message text
```

## 10. Evidence questions for the first controlled turn

The first live T1/T2/T3 run should answer:

```text
W1  Did exactly one conversation POST occur?
W2  Did the page-owned turn complete successfully?
W3  Was a conversation_id returned?
W4  Did the final page remain at root or become /c/<id>?
W5  After the disposable tab closed, can canonical get_status(id) read it?
W6  Can canonical get_messages(id) read it?
W7  Can canonical attach_conversation(id) read it?
W8  Does any Temporary proof signal become visible only after the first write?
W9  Did the isolated tab remain non-foreground?
```

History absence and TEMP/NORMAL cross-mode isolation remain separate later gates; they must not be inferred merely from canonical readability.

## 11. Architecture status

No architecture invalidation has been observed yet.

The existing split can still express the experiment:

```text
browser-owned page = mutation / product-authority plane
browserless canonical client = post-write observation plane
HDE/public runtime = still uninvolved in Temporary-specific production policy
```

However, production Temporary enablement remains blocked until the controlled-write evidence explains enough of identity, persistence, finality, and fallback behavior to define a fail-closed public contract.
