# Post-PR8 Daily-Use Product Bridge Direction

_Status: architecture direction for review before implementation_

_Date captured: 2026-08-15_

_Base evidence: green PR8.6 product-runtime/public-surface baseline_

This document captures the intended next phase of `chatgpt-web-adapter` in detail so that the reasoning is not lost between implementation PRs.

It is deliberately more detailed than a normal roadmap entry. The purpose is to preserve the full meaning of the discussion around HDE integration, Temporary Chat, runtime-tab lifecycle, latency and streaming, model selection, browser-resource cost, debugger ownership, and future research automation.

The central shift is:

> `chatgpt-web-adapter` should stop feeling like “a Python wrapper that eventually returns a ChatGPT answer” and evolve into a local ChatGPT product bridge that gives HDE fast, controllable, low-overhead, capability-aware access to ordinary ChatGPT product semantics.

The current browser-owned runtime is already usable for HDE ordinary text turns. The next phase should make it feel native for daily use: low-latency, nearly invisible when idle, explicit about product modes, and suitable as a substrate for longer automated research workflows.

---

## 1. Current baseline and what is already safe to integrate into HDE

PR8.3 through PR8.6 established a sufficiently clean HDE-facing boundary:

```text
HDE
 |
 v
ChatGPTProductRuntime
 |
 +-- CanonicalConversationClient
 |     -> attach / messages / status / session / readback
 |
 `-- ProductWriteTransport
       -> BrowserOwnedProductTransport
             -> extension-owned ordinary ChatGPT page write
```

The important consequence is that HDE no longer needs to know:

- Chrome tab IDs;
- extension worker names;
- Native Messaging implementation details;
- Sentinel internals;
- `chrome.debugger` target IDs;
- the concrete browser-owned writer class.

For new HDE integration, the intended surface is already:

```python
runtime.health(...)
runtime.capabilities()
runtime.send(...)
runtime.send_text_observed(...)
runtime.get_status(...)
runtime.get_messages(...)
runtime.attach_conversation(...)
```

The current browser-owned transport has evidence-backed support for ordinary text turns, new chat, continuation, and canonical readback. Other product features must remain capability-gated rather than assumed.

In particular, today the browser-owned capability model intentionally does **not** claim production support for:

```text
Temporary Chat
streaming
model selection / preservation
reasoning selection / preservation
files
web search
product-memory/personalization semantics
conversation branching
```

Some of these may exist in the ChatGPT product or in historical `ChatGPTWebClient` paths. That is not enough. HDE should treat a product-runtime feature as usable only when the current `ProductWriteTransport` declares it `AVAILABLE` with evidence.

Therefore:

> HDE can start using `ChatGPTProductRuntime` now, but it should integrate it as a capability-aware runtime rather than assuming the whole ChatGPT UI feature set is already available through the new transport.

---

## 2. The daily-use target

The desired end state is not merely:

```text
send prompt
wait
receive final answer
```

The desired experience is closer to:

```text
HDE requests a turn
      |
      v
reuse or create minimal browser authority
      |
      v
page-owned product write
      |
      +----> first text arrives almost immediately
      |          |
      |          +----> HDE/UI streams response incrementally
      |
      v
canonical completion proven
      |
      v
runtime becomes idle
      |
      v
TTL expires -> browser authority is closed/discarded
```

For one-shot internal HDE work, the ideal path becomes:

```text
HDE internal call
      |
Temporary Chat
      |
FAST / Instant-like product mode
      |
streaming
      |
canonical finality
      |
close runtime tab immediately or after a very short TTL
```

The long-term resource target is intentionally aggressive:

```text
idle product-runtime CPU ~= 0
no unnecessary foreground disturbance
runtime tab may not exist while idle
no repeated full page initialization inside an active burst
browserless canonical reads where possible
browser authority used only when product write semantics require it
explicit Temporary Chat for ephemeral HDE work
```

The browser should increasingly behave like a **product-authority peripheral**, not like the place where the user is expected to consume the answer.

---

# Part I — Runtime-tab lifecycle and TTL

## 3. A reusable tab should not mean an immortal tab

The current design correctly supports a reusable runtime tab because repeated cold starts are expensive and because the page environment owns the protected product write.

However, “reusable” should not become “keep a heavy ChatGPT page alive forever.”

The runtime needs an explicit lifecycle policy.

A likely public configuration shape is:

```python
runtime = assemble_product_runtime(
    runtime_tab_policy="idle-ttl",
    runtime_tab_ttl=300,
)
```

The exact names are not frozen yet, but the semantics should support at least three policies.

### `PERSISTENT`

```text
create/recover runtime tab
        |
        v
reuse while Chrome/browser runtime lives
```

Use when:

- the user is actively working through many turns;
- cold-start latency matters more than idle resource cost;
- a long research session is in progress.

This is close to the current behavior.

### `IDLE_TTL`

```text
turn completes
     |
     v
start idle timer
     |
     +-- next turn before expiry -> cancel timer and reuse tab
     |
     `-- timer expires -> safely close/discard runtime tab
```

This should probably become the daily-use default.

Example:

```python
runtime_tab_ttl = 300  # five minutes after the last completed turn
```

A burst of HDE activity then pays one cold start, while an abandoned session stops consuming browser resources after the TTL.

### `TURN_SCOPED`

```text
create/reuse
   |
write
   |
stream/read
   |
canonical finality
   |
close
```

This is particularly attractive for one-shot Temporary Chat calls.

The key safety rule is:

> `TURN_SCOPED` must mean “close after safe turn completion,” not “close immediately after the UI submit action.”

The product page may still be involved in producing or maintaining the turn after the initial input event. The runtime must not destroy its browser authority merely because text insertion or submission was observed.

---

## 4. TTL starts after finality, not after submission

A naive implementation could do this:

```text
submit
 -> start TTL
 -> close tab
```

That is unsafe because the write may have been accepted while the assistant response is still being generated.

The intended lifecycle is:

```text
page-owned write
      |
      v
write accepted / observed
      |
      v
streaming and/or canonical observation
      |
      v
canonical finality proven
      |
      v
turn lease released
      |
      v
start idle TTL
      |
      v
close/discard after expiry
```

For a one-shot temporary turn with `ttl=0`:

```text
Temporary Chat
 -> write
 -> stream
 -> canonical finality
 -> close immediately
```

The zero-TTL case therefore remains safe because “zero” is measured after finality.

---

## 5. Runtime-tab lease semantics

The lifecycle should be expressed internally as a lease rather than as an arbitrary timer attached to a tab ID.

Conceptually:

```text
TAB ABSENT
   |
   | acquire
   v
TAB LEASED / ACTIVE
   |
   | write + response lifecycle
   v
TAB LEASED / FINALIZING
   |
   | canonical finality
   v
TAB IDLE
   |
   | TTL
   v
TAB CLOSABLE
   |
   v
TAB ABSENT
```

Important invariants:

1. An in-flight turn holds the lease.
2. A canonical-readback wait holds the lease unless independent evidence proves the page is no longer required.
3. A second turn must not race with tab disposal.
4. Disposal must be fenced against a new lease acquisition.
5. A stale stored tab ID must continue to reconcile correctly.
6. Closing a runtime tab must not be interpreted as a failed turn after canonical completion has already been proven.
7. If disposal fails, the product response should still remain successful; disposal is a lifecycle concern, not response validity.

Suggested observability:

```text
runtime_tab_policy
runtime_tab_ttl_seconds
runtime_tab_lease_acquired
runtime_tab_idle_since
runtime_tab_disposal_requested
runtime_tab_disposal_reason
runtime_tab_closed
runtime_tab_discarded
runtime_tab_reused_before_expiry
```

---

## 6. Close versus discard should be measured, not guessed

There are at least two browser-resource strategies worth comparing:

```text
CLOSE
  remove runtime tab entirely

DISCARD
  unload page/process resources while keeping tab identity/browser entry
```

Neither should be assumed superior without measurements.

Potential tradeoff:

```text
close:
  + clean idle state
  + no tab entry
  + strongest resource release
  - next call pays full cold creation/navigation cost

discard:
  + may retain some browser/tab lifecycle state
  + possible cheaper recovery
  - tab remains present
  - next use still requires page reload
```

The project should measure:

- memory after idle transition;
- CPU after idle transition;
- next-turn cold/warm latency;
- navigation cost;
- extension reconciliation complexity;
- foreground activation risk;
- stale tab identity behavior.

The policy can remain configurable if both modes have legitimate use cases.

---

# Part II — Temporary Chat as an HDE primitive

## 7. Why Temporary Chat matters for HDE

HDE should not have to create a durable visible ChatGPT conversation for every internal inference call.

There are many calls where persistence is undesirable:

- classification;
- rewriting an internal note;
- extracting structured information;
- generating a temporary candidate;
- evaluating whether a research goal is complete;
- planning the next instruction in a longer research loop;
- short internal reasoning that should not clutter the user’s ChatGPT conversation list.

The desired architecture is:

```text
HDE
|
+-- DURABLE_PRODUCT_CHAT
|     persistent ordinary ChatGPT conversation
|     user-visible continuity when intentionally desired
|
`-- EPHEMERAL_PRODUCT_CHAT
      Temporary Chat semantics
      one-shot or short-lived internal work
      HDE supplies its own reviewed context
```

This is especially compatible with HDE’s own memory architecture.

The long-term mental model is:

```text
HDE canonical/reviewed memory
          |
          v
bounded context projection
          |
          v
Temporary Chat product turn
          |
          v
response
          |
          v
HDE decides what, if anything, becomes durable HDE memory
```

The ChatGPT product should not accidentally become the owner of HDE’s internal memory policy.

---

## 8. Temporary Chat must be characterized, not assumed

The current product capability is intentionally `UNKNOWN`.

PR8.7 should therefore begin as a live characterization PR.

Desired properties to verify include:

```text
T0  product Temporary mode can be selected by the browser-owned runtime
T1  ordinary text turn succeeds under that mode
T2  response streaming/readback still works
T3  canonical finality can still be proven
T4  the resulting turn does not become an ordinary persistent-history conversation
T5  no accidental normal-chat fallback occurs when Temporary mode selection fails
T6  continuation semantics are explicitly characterized rather than assumed
T7  provenance records the requested/observed conversation mode
T8  capability changes UNKNOWN -> AVAILABLE only after live evidence
```

If product semantics differ from these expectations, the capability model should record the actual behavior rather than force the desired abstraction.

Fail-closed rule:

> If the caller explicitly requests Temporary Chat and the transport cannot prove that Temporary mode was selected, it must fail before the write rather than silently creating a normal durable chat.

Possible API direction:

```python
runtime.send(
    prompt,
    conversation_mode="temporary",
)
```

or:

```python
runtime.send_temporary(prompt)
```

The exact surface should be decided after live characterization.

---

## 9. Temporary Chat and TTL naturally compose

The strongest one-shot HDE primitive becomes:

```python
runtime.send(
    internal_prompt,
    conversation_mode="temporary",
    model_profile="fast",
    runtime_tab_ttl=0,
    on_token=...,
)
```

Conceptually:

```text
HDE internal question
        |
        v
Temporary Chat
        |
        v
fast product model/mode
        |
        v
stream response immediately
        |
        v
canonical finality
        |
        v
close runtime tab
        |
        v
no long-lived browser cost
```

That is close to an ideal internal inference substrate for HDE while preserving ordinary ChatGPT product ownership of the write.

---

# Part III — Streaming and perceived latency

## 10. The current latency problem is architectural, not imagined

The current browser-owned production path accepts `on_token`, but it does not provide real incremental streaming.

The effective shape today is:

```text
page-owned write
     |
     v
poll canonical status
     |
     v
poll canonical messages
     |
     v
wait for a NEW FINAL assistant message
     |
     v
construct ChatResponse
     |
     v
on_token(full_response_text) once
```

This explains an important observed UX failure:

```text
ChatGPT page:
  assistant has visibly finished or mostly finished

HDE / CLI:
  still waiting for canonical final-message polling
  possibly several additional seconds
```

The current path was designed around trustworthy finality. That is correct for correctness, but it is not sufficient for responsive UI.

The next design must separate:

```text
TEXT AVAILABILITY
        !=
CANONICAL FINALITY
```

This distinction is one of the most important post-PR8 architectural changes.

---

## 11. Desired response lifecycle

The runtime should expose a turn as a sequence of independently meaningful stages:

```text
T0  request accepted by local runtime
T1  browser write delegated
T2  product write accepted/observed
T3  first assistant text delta observed
T4  additional text deltas
T5  last visible/canonical text delta
T6  canonical finality proven
T7  lifecycle cleanup / TTL starts
```

HDE should be able to render from `T3` onward.

A successful final `ChatResponse` should still only be considered authoritative after `T6`.

Conceptual event flow:

```python
on_event(TurnStarted(...))
on_event(WriteAccepted(...))
on_token("The first ")
on_token("part of the ")
on_token("answer arrives...")
on_event(CanonicalCompletion(...))
```

This preserves both goals:

```text
low perceived latency
+
strong canonical completion semantics
```

---

## 12. Streaming must not weaken finality governance

Streaming text is an observation channel, not proof that the turn is complete.

The runtime should be able to say:

```text
streaming_started = true
partial_text_observed = true
canonical_completion_proven = false
```

and later:

```text
canonical_completion_proven = true
final_message_id = ...
```

If a stream stalls after partial text:

- do not report a completed response;
- do not synthesize a finish reason;
- do not automatically resend the prompt;
- reconcile using canonical conversation state.

The existing no-automatic-retry invariant remains unchanged.

---

## 13. Candidate streaming sources

The project should investigate the least coupled observation source first.

### Candidate A — Incremental canonical read

Attempt to use browserless canonical reads during generation:

```text
write accepted
   |
   v
get_messages()
   |
   v
assistant message exists and text grows
   |
   v
emit only newly observed suffix
```

If the canonical read surface exposes partial assistant text while generation is in progress, this is the preferred architecture.

Benefits:

- no extra DOM coupling;
- no rendered UI dependence;
- browser remains write authority only;
- same canonical plane already used for finality;
- HDE receives text without learning browser details.

Required correctness work:

- stable message identity during generation;
- monotonic-text assumptions must be tested, not assumed;
- handle rewrites/replacements rather than only appends;
- avoid duplicate token emission;
- distinguish temporary thinking/placeholder text from final answer content if applicable;
- reconcile final canonical text against streamed text.

### Candidate B — Safe browser network observation

If canonical reads do not expose useful partial text, the extension may observe the product response stream.

Important boundary:

```text
browser sees product response
       |
       v
extension emits only safe assistant text/event deltas
```

It must not export:

- cookies;
- Authorization headers;
- Sentinel/protection credentials;
- Turnstile material;
- raw request headers;
- unrelated private network payloads.

This can preserve low latency while keeping browser security context browser-local.

### Candidate C — Rendered page observation

A `MutationObserver`, Accessibility observation, or equivalent rendered-page channel is a fallback if neither canonical nor safe network observation is sufficient.

This is less desirable because:

- DOM structure changes frequently;
- rendered text can differ from canonical message representation;
- transient UI nodes may appear/disappear;
- implementation becomes more browser/page coupled.

It may still be useful as a latency observation channel if canonical finality remains authoritative.

---

## 14. Streaming metrics should become first-class

PR8.9 should measure at least:

```text
local_request_start_ms
browser_write_accepted_ms
first_text_observed_ms
last_text_delta_ms
canonical_completion_ms
response_returned_ms
```

Derived metrics:

```text
TTFW  = time to first write acceptance
TTFT  = time to first text
stream_duration
finality_lag = canonical_completion - last_text_delta
return_lag   = response_returned - canonical_completion
```

The user-visible problem today is largely `finality_lag + return_lag` being paid before any text is surfaced.

The goal is not necessarily to make canonical finality instantaneous. The goal is to stop blocking text presentation on finality when a safe partial observation already exists.

---

# Part IV — Product model and reasoning selection

## 15. HDE needs fast and deep product modes

Not every HDE turn deserves a slow reasoning model.

Examples:

```text
simple extraction          -> FAST
classification             -> FAST
short rewriting            -> FAST
ordinary conversation      -> FAST / BALANCED
research synthesis         -> DEEP
architecture review        -> DEEP
hard scientific reasoning  -> DEEP / MAX
```

The product runtime should support explicit model/reasoning intent rather than always inheriting whichever mode happens to be selected in the browser UI.

The current capabilities remain `UNKNOWN`; implementation must begin with product characterization.

---

## 16. Prefer semantic model profiles over hard-coded product names

A brittle API would expose only:

```python
model="some-current-product-model-name"
```

Product model names and picker organization can change over time.

HDE is better served by semantic intent:

```python
runtime.send(
    prompt,
    model_profile="fast",
)
```

Possible profiles:

```text
FAST
BALANCED
DEEP
MAX
```

Conceptually:

```text
FAST      -> current low-latency / Instant-like product mode
BALANCED  -> normal general-purpose product mode
DEEP      -> current reasoning / Thinking-like product mode
MAX       -> highest-cost/deepest available product mode
```

The mapping is transport/product-specific and should be capability-observed.

An advanced exact selector may still be useful:

```python
model_exact="..."
```

but it should not be the only abstraction available to HDE.

---

## 17. Model selection must be provenance-aware

No silent model drift.

A turn should be able to report:

```json
{
  "requested_model_profile": "FAST",
  "requested_model_exact": null,
  "selected_product_mode": "...",
  "observed_model": "...",
  "selection_preserved": true
}
```

If the transport cannot honor an explicit model request, behavior should be explicit:

```text
STRICT selection
  -> fail before write if requested mode cannot be selected/proven

BEST_EFFORT selection
  -> continue only if caller explicitly allowed fallback
  -> provenance records requested vs observed
```

Do not silently claim that the user requested a fast model when the page actually ran a deep reasoning mode.

---

## 18. Temporary + FAST + streaming is the key HDE internal path

The three features together are much more valuable than each feature independently.

```text
Temporary Chat
   +
FAST model profile
   +
streaming
   +
TTL=0 after finality
```

creates an HDE primitive with these desired properties:

```text
low first-token latency
no durable ChatGPT history clutter
minimal browser lifetime
canonical completion evidence
HDE-owned memory/context policy
```

This should be treated as a first-class product target, not an accidental combination of flags.

---

# Part V — Browser authority cost and debugger ownership

## 19. The debugger warning should not be “hidden” by bypassing browser UX

The current browser-owned implementation uses `chrome.debugger` / CDP as part of browser interaction.

A browser warning indicating that a debugging API is controlling the page is an intentional browser security/authority signal.

The project should **not** pursue a trick whose goal is to conceal or bypass that warning.

The legitimate engineering goals are instead:

1. minimize how long debugger attachment is held;
2. detach immediately after the operation that actually needs it;
3. determine whether the same product write can be implemented with a lower-authority browser primitive;
4. ultimately remove the debugger dependency if a proven alternative exists.

The right question is:

> Can we stop requiring `chrome.debugger` for the production write path?

not:

> How do we hide Chrome’s debugger warning?

---

## 20. Candidate lower-authority browser path

PR8.11/PR9.0 should investigate whether a content-script/scripting path can replace CDP for the required page interaction.

Possible shape:

```text
extension
  |
  +-- content script / chrome.scripting
  +-- composer readiness observation
  +-- ordinary DOM interaction where product semantics accept it
  +-- MutationObserver or page events for response observation
```

Potential benefits if independently proven:

```text
no debugger permission
no debugger warning bar
smaller browser authority surface
simpler runtime lifecycle
less attach/detach state
```

But this must be a live evidence question.

Programmatically generated DOM events, content-script interaction, and CDP input do not automatically have equivalent product semantics. The current proven path must remain the baseline until an alternative independently passes product-semantic and reliability gates.

---

## 21. Browser page cost should be measured before optimization

The current runtime may be paying for:

```text
full ChatGPT app initialization
JavaScript bundles
DOM construction
styles/layout
network assets
React/application state
background timers/work
possible GPU/compositor work
```

Many of those costs may be irrelevant to HDE because HDE does not consume the rendered page.

However, resource blocking must not be guessed.

The project should first establish a resource baseline:

```text
cold boot CPU time
cold boot wall time
network bytes transferred
request count
steady idle CPU
steady idle memory
JS heap if available
DOM node count if available
GPU/compositor activity if measurable
per-turn CPU
per-turn network overhead
navigation/reload cost
```

Then experiments can remove or suspend resource classes one at a time.

The invariant is:

> Do not break or approximate product semantics merely to make the page lighter.

---

## 22. The ideal browser lifecycle

The long-term browser-side state machine is approximately:

```text
ABSENT
  |
  | request
  v
BOOTING
  |
  v
READY
  |
  v
ACTIVE WRITE
  |
  v
STREAMING / OBSERVING
  |
  v
CANONICAL FINALITY
  |
  v
QUIESCENT
  |
  | TTL
  v
DISPOSED
```

The runtime should spend almost all idle time in either:

```text
QUIESCENT with near-zero activity
```

or preferably:

```text
ABSENT / DISPOSED
```

if the TTL has expired.

---

## 23. Evidence correction: foreground activation is not a guaranteed invariant

Earlier warm-path validation demonstrated successful inactive runtime-tab reuse.

A later live compatibility gate demonstrated a different cold/no-tab case:

```text
runtime_tab_preexisting        false
runtime_tab_created_for_turn   true
foreground_activation_observed true
```

while governance still correctly reported:

```text
runtime_tab_foreground_activation_requested false
```

Therefore the precise statement is:

```text
runtime does not intentionally request foreground activation
```

but **not**:

```text
foreground activation can never occur
```

This should become a measurable PR8.8/PR8.11/PR9.0 criterion:

```text
cold-start foreground-disturbance risk
warm-reuse foreground-disturbance risk
```

The lifecycle work should try to reduce this risk, but provenance must continue reporting what was actually observed.

---

# Part VI — Research workflow automation

## 24. The current manual research loop is already an algorithm

A common current workflow is:

```text
research goal
    |
    v
send task to long-lived research chat
    |
    v
wait for model to finish
    |
    v
read answer
    |
    v
next step is already obvious or stated in the answer
    |
    v
manually send “continue” / next instruction
    |
    v
repeat
```

The human is often acting as a lightweight turn controller rather than inventing every next step from scratch.

That means a large part of the workflow is automatable.

The important architectural question is **where** the automation belongs.

---

## 25. `chatgpt-web-adapter` should expose primitives; HDE should own research policy

It is tempting to put the entire research agent inside `chatgpt-web-adapter` because the repository already owns ChatGPT conversation access.

The better boundary is:

### Adapter responsibility

```text
send
stream
status
messages
attach
Temporary Chat
model/reasoning selection
tab lease / TTL
completion/finality events
provenance
reconciliation
safe cancellation if independently supported later
```

### HDE / Research Runtime responsibility

```text
what should be asked next?
should the research continue?
which hypothesis should be pursued?
when is the goal complete?
when is human review required?
what budget applies?
what context should be projected?
```

This separation matters because the product transport may change completely after PR9.0 while the research policy should remain intact.

If a native daemon or future supported product interface replaces the current browser-owned transport, HDE research logic should not need to be rewritten.

---

## 26. Temporary planner pattern

A particularly strong design is to use the main durable research chat for the actual investigation and a separate ephemeral call to decide the next instruction.

```text
                  MAIN RESEARCH CHAT
                         |
                         | completed response
                         v
                  Research Controller
                         |
                         v
                  TEMPORARY PLANNER
                    FAST model
                         |
                         | next-step proposal
                         v
                  policy / validation
                         |
                         v
                  MAIN RESEARCH CHAT
```

Example:

```text
Main research response:
  “The current evidence supports X. The next useful experiment is Y.”

Temporary planner:
  goal + recent response + policy
  -> “Continue by testing Y, with explicit comparison of A/B/C and stop if Z.”

Controller:
  validate budget / duplicate / stop rules
  -> send to main research conversation
```

The planner does not need to pollute ChatGPT history. It may be a perfect `Temporary Chat + FAST + TTL=0` consumer.

---

## 27. Research controller should be more than automatic “continue”

A useful controller eventually looks like:

```text
GOAL
  “investigate mechanism X”

MAIN MODEL
  deep / reasoning profile

PLANNER
  fast + temporary

EVALUATOR
  fast + temporary

loop:
    receive streamed main response
    wait for canonical finality

    evaluator:
        goal achieved?
        contradiction found?
        evidence missing?
        answer incomplete?
        next experiment needed?

    if DONE:
        stop

    planner:
        construct next instruction

    policy:
        safe?
        duplicate?
        within budget?
        external action?
        human checkpoint required?

    send to main research chat
```

This turns the current manual monitoring loop into a deterministic, auditable workflow.

---

## 28. Automation guards are required from the first version

Even a simple continuation controller should not run without bounded policy.

Minimum guards:

```text
max_turns
max_runtime
max_failures
max_consecutive_low-value_turns
no automatic resend after ambiguous write
duplicate-turn fingerprint / similarity check
persistent job journal
explicit stop state
human gate for tool/external actions
stop on planner uncertainty above threshold
stop on repeated contradiction/no-progress
```

A useful mental model is not “fully autonomous agent.”

It is:

> A bounded research loop that removes repetitive monitoring and obvious continuation work while preserving clear stop, review, and failure boundaries.

---

# Part VII — Proposed implementation sequence

## 29. PR8.7 — Temporary Chat Product Semantics, Ephemeral Conversation Lifecycle and Fail-Closed Governance

### Goal

Make Temporary Chat a proven product-runtime capability suitable for ephemeral HDE calls.

### Work

- characterize actual product Temporary Chat selection through the browser-owned transport;
- define explicit conversation mode request;
- prove no silent durable-chat fallback;
- characterize new-chat/continuation behavior;
- preserve canonical completion/readback;
- add conversation-mode provenance;
- move `temporary_chat` from `UNKNOWN` only after live evidence;
- define how Temporary Chat interacts with HDE context and product personalization observations without overclaiming semantics.

### Core invariant

```text
TEMPORARY requested
    -> temporary product mode proven before write
or
    -> fail closed
```

No accidental durable conversation creation.

---

## 30. PR8.8 — Runtime Tab Lease / Idle-TTL, Turn-Scoped Disposal and Cold/Warm Lifecycle Governance

### Goal

Stop treating the reusable runtime tab as an immortal resource.

### Work

- explicit lifecycle policy;
- `PERSISTENT`, `IDLE_TTL`, and `TURN_SCOPED` semantics;
- TTL begins only after canonical finality;
- lease/disposal fencing;
- no disposal during in-flight turn;
- temporary one-shot `ttl=0` path;
- close vs discard characterization;
- cold/warm creation/reuse observations;
- foreground disturbance metrics;
- safe recovery when the user manually closes the runtime tab.

### Core invariant

```text
no tab disposal before the turn no longer needs browser authority
```

---

## 31. PR8.9 — Incremental Response Streaming, First-Delta Latency and Canonical-Finality Separation

### Goal

Make HDE receive useful text as soon as it exists instead of waiting for the final-message polling loop.

### Work

- prove the best partial-text observation source;
- emit real incremental `on_token` / event deltas;
- keep final canonical response authoritative;
- measure TTFT and finality lag;
- detect duplicate/rewritten partial text safely;
- reconcile streamed text with final canonical text;
- do not weaken ambiguous-write handling;
- capability changes `streaming: UNKNOWN -> AVAILABLE` only after live evidence.

### Core invariant

```text
partial text may be shown early
completion is not claimed until canonical finality is proven
```

---

## 32. PR8.10 — Product Model / Reasoning Selection, Semantic Model Profiles and Selection Provenance

### Goal

Allow HDE to deliberately choose low-latency versus deep-reasoning product behavior.

### Work

- characterize current product model/reasoning selector surface;
- semantic profiles such as `FAST`, `BALANCED`, `DEEP`, `MAX`;
- optional exact model/mode escape hatch;
- strict vs explicit best-effort fallback policy;
- requested/selected/observed model provenance;
- selection-preservation verification;
- no silent drift from requested mode;
- capability updates only for proven selection/preservation behavior.

### Core invariant

```text
requested model intent must never be silently represented as honored when evidence says otherwise
```

---

## 33. PR8.11 — Browser Authority Cost Reduction, Debugger Attachment Minimization and Resource Baseline

### Goal

Reduce browser overhead and browser-visible authority while preserving product semantics.

### Work

- cold/warm CPU, RAM, network, page-init baseline;
- idle resource baseline;
- attach/detach lifetime measurement for `chrome.debugger`;
- minimize debugger attachment duration where safe;
- investigate content-script / `chrome.scripting` alternative;
- investigate page-resource reduction only with evidence;
- compare close vs discard;
- quantify cold-start foreground disturbance;
- characterize whether any lower-authority mechanism can replace CDP without changing product semantics.

### Explicit non-goal

Do not attempt to conceal or bypass Chrome security UI while continuing to use debugger authority.

The desired outcome is to remove/minimize the authority, not hide its indication.

---

## 34. PR9.0 — Next-Generation Product Bridge Architecture Feasibility

PR9.0 should happen **after** PR8.7–PR8.11 provide real daily-use measurements.

It remains an architecture-decision PR, not a rewrite PR.

The comparison should include at least:

```text
A  current Python-centered runtime + normal inactive tab
B  optimized lightweight inactive-tab runtime
C  extension-first product bridge
D  native daemon + extension
E  extension/offscreen/embedded experiments where product semantics are proven
F  direct CDP alternative
G  any newly documented supported product surface
```

Comparison dimensions should include:

```text
product-semantic fidelity
browser ownership clarity
canonical-read independence
HDE coupling
first-token latency
finality lag
cold-start latency
idle CPU/RAM
network/page-init cost
foreground disturbance
model-control fidelity
Temporary Chat fidelity
streaming fidelity
failure isolation
language independence
install/update complexity
credential/security boundary
session continuity
ambiguous-write handling
observability/reconciliation
testability
cross-platform portability
migration cost
```

PR9.0 should end in an explicit decision, for example:

```text
DECISION: EVOLVE_CURRENT_ARCHITECTURE
```

or:

```text
DECISION: PROTOTYPE_NATIVE_DAEMON_BRIDGE
```

with measurable reasons.

---

# Part VIII — HDE integration strategy during this work

## 35. Do not wait for PR9.0 to start HDE integration

The library is already useful enough to wire into HDE for ordinary text turns.

The recommended HDE approach is:

```text
HDE model/product runtime adapter
          |
          v
ChatGPTProductRuntime
```

with capability checks before optional behavior.

Example conceptual policy:

```python
caps = runtime.capabilities()

if caps.state("temporary_chat") == "AVAILABLE":
    # use ephemeral internal mode when appropriate
    ...

if caps.state("streaming") == "AVAILABLE":
    # render incrementally
    ...

if caps.state("model_selection") == "AVAILABLE":
    # apply HDE model profile policy
    ...
```

HDE should not import browser-native implementation modules to gain these features.

---

## 36. Suggested HDE call classes

Eventually HDE may distinguish calls approximately like this:

### User-visible durable conversation

```text
mode: durable
model: FAST/BALANCED by default
streaming: yes
TTL: moderate (for active conversation reuse)
```

### Internal short inference

```text
mode: temporary
model: FAST
streaming: optional but preferred
TTL: 0 or very short
```

### Deep research step

```text
mode: durable research conversation
model: DEEP/MAX
streaming: yes
TTL: long enough to preserve warm research session
```

### Planner/evaluator call

```text
mode: temporary
model: FAST
streaming: usually not required for UI, but useful for latency
TTL: 0
```

This keeps HDE policy readable while allowing the underlying transport to evolve.

---

# Part IX — Long-term north star

## 37. The end-state mental model

The desired architecture increasingly resembles:

```text
                         HDE
                          |
                 local runtime contract
                          |
                          v
                ChatGPT Product Bridge
              /          |           \
             /           |            \
      durable chat   temporary chat   model policy
             \           |            /
              \          |           /
                       streaming
                          |
                  canonical finality
                          |
                          v
              lightweight browser authority
                          |
                  lease / TTL / close
```

Or from a resource-ownership perspective:

```text
                HDE
                 |
         lightweight local IPC/API
                 |
                 v
       ChatGPT Product Runtime
        /                 \
       /                   \
canonical/session      browser authority
network plane          only when required
       \                   /
        \                 /
          ordinary ChatGPT product
```

The browser becomes a short-lived product-authority component.

It is not the user interface HDE depends on.

It is not where HDE stores its memory.

It is not where research policy lives.

It is not the public contract.

---

## 38. What belongs in `chatgpt-web-adapter`

The project should continue growing in the direction of **transport and product-runtime primitives**:

```text
health
capabilities
send
stream
status
messages
attach
Temporary Chat
model/reasoning selection
conversation mode provenance
completion provenance
runtime-tab lease / TTL
reconciliation
browser-resource observations
```

These belong here because they describe how a local application safely and efficiently uses the ChatGPT product.

---

## 39. What should remain above the adapter

The project should resist becoming the owner of application cognition/policy.

These belong in HDE or another orchestration layer:

```text
research goals
next-step generation
planner/evaluator policy
memory selection
relationship continuity
consent policy
agent tool policy
workflow budget
human-review checkpoints
stop criteria
```

The adapter can make those workflows possible without defining their meaning.

---

## 40. Practical vision

A future HDE research session should feel approximately like this:

```text
User starts/continues a research goal
            |
            v
HDE chooses DEEP research chat
            |
            v
browser authority is reused or created
            |
            v
answer begins streaming almost immediately
            |
            v
HDE UI can display/use partial answer
            |
            v
canonical finality proven
            |
            v
Temporary FAST planner decides obvious next step
            |
            v
policy checks budget / duplication / stop conditions
            |
            v
next instruction is sent automatically
            |
            v
repeat until completion or review checkpoint
            |
            v
idle TTL expires
            |
            v
browser authority closes
```

The user should no longer need to continuously monitor a ChatGPT tab merely to see whether the model has finished and type an obvious “continue.”

At the same time, the system should remain auditable, bounded, and explicit about what was requested, what product mode was used, what text was only partial, when canonical completion was proven, and why an automated continuation was allowed.

---

# 41. Review questions before implementation

This document intentionally freezes the direction before PR8.7 implementation.

During docs review, explicitly decide:

1. Should `IDLE_TTL` become the default tab policy or remain opt-in initially?
2. Should `ttl=0` be permitted only for Temporary Chat or for any turn-scoped call?
3. Should tab disposal default to close or should close/discard be benchmarked first?
4. What exact evidence is sufficient to mark `temporary_chat` as `AVAILABLE`?
5. Should Temporary Chat be a `conversation_mode` argument or a dedicated method?
6. What source should PR8.9 prioritize for streaming: incremental canonical reads, safe browser-network deltas, or page observation?
7. Should streamed text be represented as token callbacks, text-delta events, snapshots, or more than one form?
8. What consistency contract should exist between streamed text and the final canonical message?
9. Should semantic model profiles be part of the generic `ProductWriteTransport` protocol or layered above transport capabilities?
10. Should unsupported strict model selection fail before write by default?
11. How aggressively should debugger attachment lifetime be minimized before investigating a debugger-free path?
12. Which resource metrics are required before making page-resource-blocking decisions?
13. Should the first HDE Research Runner live in `hde-shell`, a separate HDE runtime package, or another dedicated repository/module?
14. What minimum automation guards are mandatory before one research conversation can self-continue?
15. Should PR9.0 remain after PR8.11, or should an earlier architecture checkpoint occur if PR8.7–PR8.9 reveal a fundamental limitation?

---

# 42. Proposed order

```text
PR8.6   Public-surface / compatibility boundary        COMPLETE
   |
   v
PR8.7   Temporary Chat product semantics
   |
   v
PR8.8   Runtime tab lease / TTL / disposal
   |
   v
PR8.9   Incremental streaming + canonical finality split
   |
   v
PR8.10  Model / reasoning selection + semantic profiles
   |
   v
PR8.11  Browser authority cost + debugger minimization
   |
   v
PR9.0   Next-generation bridge architecture decision
```

HDE integration can proceed in parallel from the current PR8.6 baseline rather than waiting for the entire sequence.

A first HDE Research Runner can also begin in parallel once streaming/Temporary/model controls have enough evidence for the desired workflow.

---

# 43. Final statement

The long-term objective is no longer just:

> “Make ChatGPT callable from Python.”

The stronger objective is:

> Build a small local ChatGPT product bridge that lets HDE and other local tools use ordinary ChatGPT product semantics with low latency, explicit capability/provenance contracts, temporary or durable conversation modes, deliberate model selection, bounded browser lifetime, and a replaceable browser/write implementation.

The current browser-owned tab is the first proven authority mechanism behind that contract. It should not become the contract itself.

The intended daily-use experience is:

```text
idle:
    browser authority absent or nearly free

request:
    create/reuse authority
    perform page-owned write
    stream text as soon as safely observed

completion:
    canonical finality proven

post-completion:
    keep warm only for the configured TTL
    then close/discard

Temporary one-shot:
    temporary mode
    fast model
    stream
    finality
    close immediately

research automation:
    durable main research chat
    temporary fast planner/evaluator
    bounded automatic continuation
    human review when policy requires it
```

That is the direction to preserve through PR8.7–PR9.0 review and implementation.