# Post-PR8 Daily-Use Product Bridge Direction

_Status: architecture direction after full design review; implementation-ready for PR8.7 planning_

_Date captured: 2026-08-15_

_Architecture review incorporated: 2026-08-15_

_Base evidence: green PR8.6 product-runtime/public-surface baseline_

This document captures the intended next phase of `chatgpt-web-adapter` in detail so that the reasoning is not lost between implementation PRs.

It is deliberately more detailed than a normal roadmap entry. The purpose is to preserve the full meaning of the discussion around HDE integration, Temporary Chat, runtime-tab lifecycle, latency and streaming, model selection, browser-resource cost, debugger ownership, and future research automation.

The central shift is:

> `chatgpt-web-adapter` should stop feeling like “a Python wrapper that eventually returns a ChatGPT answer” and evolve into a local ChatGPT product bridge that gives HDE fast, controllable, low-overhead, capability-aware access to ordinary ChatGPT product semantics.

The current browser-owned runtime is already usable for HDE ordinary text turns. The next phase should make it feel native for daily use: low-latency, nearly invisible when idle, explicit about product modes, and suitable as a substrate for longer automated research workflows.

---

## 0. Evidence vocabulary for this document

This document intentionally separates what has already been demonstrated from what is merely desired or still needs characterization.

Use the following labels when interpreting or extending it:

```text
PROVEN
    demonstrated by current implementation/tests/live evidence

TARGET
    desired end-state behavior; not yet a claim about the current runtime

HYPOTHESIS
    plausible architectural opportunity that requires live characterization

DECISION
    architecture-review decision adopted for the next implementation sequence

DECISION_PENDING
    deliberately unresolved until measurements or live product evidence exist
```

Examples:

```text
PROVEN
    browser-owned ordinary text new-chat and continuation work

PROVEN
    canonical browserless readback can prove completion even when finish_reason is null

PROVEN
    warm runtime-tab reuse has been observed without foreground activation

PROVEN
    a cold/no-tab creation path has also been observed to foreground the new tab

TARGET
    idle browser-authority CPU approximately zero

TARGET
    low-latency incremental text observation before canonical finality

HYPOTHESIS
    browser authority may become releasable before canonical finality

DECISION_PENDING
    whether DISCARD has enough benefit over CLOSE to justify production support
```

A future contributor should not silently promote a `TARGET` or `HYPOTHESIS` into a `PROVEN` statement merely because the desired design sounds natural.

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

The current browser-owned transport has evidence-backed support for ordinary text turns, new chat, continuation, and canonical readback.

Other product features must remain capability-gated rather than assumed.

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

### PROVEN baseline

```text
ordinary product text turns                 PROVEN
new chat                                    PROVEN
continuation                                PROVEN
canonical readback                          PROVEN
explicit transport selection                PROVEN
no legacy write fallback                    PROVEN
capability/provenance contracts              PROVEN
public-surface compatibility boundary        PROVEN
Temporary Chat                               UNKNOWN
streaming                                    UNKNOWN
model/reasoning selection                    UNKNOWN
```

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
      +----> first useful text appears as soon as safely observable
      |          |
      |          +----> HDE/UI renders revision-safe text observations
      |
      +----> browser authority is released as soon as evidence permits
      |
      v
canonical completion proven
      |
      v
turn lifecycle completes
```

Browser-authority release and canonical finality are deliberately shown as separate events.

If live evidence proves that the page is required until canonical finality, those events happen at the same point.

If live evidence proves that generation/finality can safely continue through the canonical plane after page-owned write acceptance, browser authority may be released earlier.

For one-shot internal HDE work, the ideal path becomes:

```text
HDE internal call
      |
Temporary Chat
      |
FAST / Instant-like product mode
      |
revision-safe streaming
      |
canonical finality
      |
no durable ChatGPT history clutter
```

The long-term resource target is intentionally aggressive:

```text
idle product-runtime CPU ~= 0
no unnecessary foreground disturbance
runtime tab may not exist while idle
no repeated full page initialization inside an active burst
browserless canonical reads where possible
browser authority used only while product semantics require it
explicit Temporary Chat for ephemeral HDE work
```

The browser should increasingly behave like a **product-authority peripheral**, not like the place where the user is expected to consume the answer.

---

# Part I — Browser authority lifecycle, turn lifecycle, and TTL

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
browser authority becomes safely idle
     |
     v
start idle timer
     |
     +-- next authority lease before expiry -> cancel timer and reuse tab
     |
     `-- timer expires -> safely close/discard runtime tab
```

This is a strong candidate for a later daily-use default, but it should **not** silently become the initial PR8.8 default.

### DECISION — initial PR8.8 compatibility default

```text
PERSISTENT = initial default
IDLE_TTL   = explicit opt-in
TURN_SCOPED = explicit opt-in
```

Reason:

PR8.8 should add lifecycle control without silently changing the current proven production behavior before cold/warm/resource measurements exist.

After live characterization, a later evidence-backed decision may promote `IDLE_TTL` to the daily-use default.

Example:

```python
runtime_tab_ttl = 300  # five minutes after browser authority becomes safely idle
```

A burst of HDE activity then pays one cold start, while an abandoned session stops consuming browser resources after the TTL.

### `TURN_SCOPED`

Conceptually:

```text
create/reuse browser authority
   |
page-owned write
   |
keep authority only as long as proven necessary
   |
release authority lease
   |
TTL=0 -> close
```

This is particularly attractive for one-shot Temporary Chat calls, but it is **not restricted to Temporary Chat**.

### DECISION — `ttl=0`

`ttl=0` may be used for any explicit `TURN_SCOPED` call whose browser-authority release point is evidence-backed.

It must never mean “close immediately after the UI submit action.”

---

## 4. Turn Lifecycle Lease and Browser Authority Lease are different contracts

This is the central lifecycle decision from the architecture review.

A turn being unfinished does **not** automatically imply that the browser page still needs to exist.

The runtime therefore needs two conceptual leases.

### Turn Lifecycle Lease

Represents the full logical turn:

```text
request accepted
    |
write delegated
    |
partial observations may arrive
    |
canonical finality or reconciliation
    |
turn terminal state
```

This lease protects:

- duplicate-send governance;
- canonical completion/finality;
- reconciliation after ambiguous outcomes;
- final response/provenance construction;
- automation step lineage.

### Browser Authority Lease

Represents only the period during which the product browser context is still required:

```text
browser authority required
    |
page-owned operation
    |
product/page dependency continues if necessary
    |
EVIDENCE-BACKED AUTHORITY RELEASE POINT
    |
browser authority no longer required for this turn
```

This lease protects:

- runtime-tab creation/reuse;
- page-owned product mutation;
- any browser-local generation/observation requirement;
- disposal fencing;
- debugger/CDP attachment where still required.

### Why the split matters

The conservative current possibility is:

```text
Browser Authority Lease
===============================> canonical finality
Turn Lifecycle Lease
===============================> canonical finality
```

But a future proven path may be:

```text
Browser Authority Lease
=============> write safely handed off

Turn Lifecycle Lease
===============================> canonical finality

canonical browserless observation continues after browser release
```

That second path would let the library become materially lighter without weakening correctness.

### HYPOTHESIS — early browser-authority release

It is plausible that after a proven page-owned write/hand-off point, server-side generation and canonical observation can continue without keeping the heavy page alive.

This is **not currently assumed**.

PR8.8/PR8.9 should measure it.

---

## 5. TTL starts after Browser Authority Lease release, never merely after submission

A naive implementation could do this:

```text
submit
 -> start TTL
 -> close tab
```

That is unsafe.

The reviewed lifecycle is:

```text
page-owned write
      |
      v
write accepted / observed
      |
      v
browser still required?
      |
      +-- YES -> retain Browser Authority Lease
      |
      `-- NO  -> release Browser Authority Lease
                         |
                         v
                    start idle TTL
                         |
                         v
                    close after expiry

Turn Lifecycle Lease continues independently until:
      |
      v
canonical finality / reconciliation
```

If browser authority is proven necessary until finality, the practical path remains:

```text
write
 -> stream/observe
 -> canonical finality
 -> release Browser Authority Lease
 -> TTL
 -> close
```

For an evidence-backed one-shot turn with `ttl=0`:

```text
write
 -> browser authority no longer required
 -> release Browser Authority Lease
 -> close immediately

canonical observation/finality may already be complete
or may continue independently if proven safe
```

The safety property is therefore stronger than the earlier wording:

> Zero TTL is measured from safe browser-authority release, not from submission and not automatically from finality.

---

## 6. Browser Authority Lease state machine and disposal fencing

The lifecycle should be expressed internally as a lease rather than as an arbitrary timer attached to a tab ID.

Conceptually:

```text
TAB ABSENT
   |
   | acquire Browser Authority Lease
   v
TAB LEASED / ACTIVE
   |
   | page-owned write / required browser work
   v
TAB LEASED / RELEASABLE?
   |
   | evidence says browser no longer needed
   v
TAB IDLE
   |
   | TTL
   v
TAB CLOSABLE
   |
   | fenced disposal
   v
TAB ABSENT
```

In parallel:

```text
TURN ABSENT
   |
   | acquire Turn Lifecycle Lease
   v
TURN ACTIVE
   |
   | partial observations / finality / reconciliation
   v
TURN TERMINAL
   |
   v
Turn Lifecycle Lease released
```

Important invariants:

1. An in-flight browser operation holds the Browser Authority Lease.
2. A logical turn holds the Turn Lifecycle Lease until canonical terminal state or explicit reconciliation terminal state.
3. Canonical-readback waiting does **not** automatically hold browser authority; it holds browser authority only if evidence says the page remains required.
4. A second turn must not race with tab disposal.
5. Disposal must be fenced against a new Browser Authority Lease acquisition.
6. A stale stored tab ID must continue to reconcile correctly.
7. Closing a runtime tab must not be interpreted as a failed turn after the browser-authority release point has been safely crossed.
8. If disposal fails, product response validity must not be retroactively invalidated; disposal is a lifecycle concern.
9. If the browser is manually closed while authority is still required, the turn must enter an explicit failure/reconciliation path rather than being silently retried.
10. The system must distinguish `browser authority released` from `turn completed` in provenance and metrics.

Suggested observability:

```text
runtime_tab_policy
runtime_tab_ttl_seconds
turn_lifecycle_lease_acquired
turn_lifecycle_lease_released
browser_authority_lease_acquired
browser_authority_release_reason
browser_authority_released_at_ms
runtime_tab_idle_since
runtime_tab_disposal_requested
runtime_tab_disposal_reason
runtime_tab_closed
runtime_tab_discarded
runtime_tab_reused_before_expiry
```

---

## 7. Runtime-level defaults and per-turn TTL overrides need explicit precedence

The document uses both runtime configuration and per-turn overrides intentionally.

Example runtime default:

```python
runtime = assemble_product_runtime(
    runtime_tab_policy="idle-ttl",
    runtime_tab_ttl=300,
)
```

Example per-turn override:

```python
runtime.send(
    prompt,
    runtime_tab_policy="turn-scoped",
    runtime_tab_ttl=0,
)
```

### DECISION — precedence

```text
per-turn explicit override
        ↓
runtime assembly default
        ↓
transport implementation default
```

Absence of a per-turn value means “inherit,” not “reset.”

Every effective lifecycle decision should be observable in provenance/governance so callers can distinguish:

```text
requested policy
effective policy
requested TTL
effective TTL
release point evidence
actual disposal outcome
```

---

## 8. Close versus discard should be measured, but CLOSE is production v1

There are at least two browser-resource strategies worth comparing:

```text
CLOSE
  remove runtime tab entirely

DISCARD
  unload page/process resources while keeping tab identity/browser entry
```

Potential tradeoff:

```text
close:
  + clean idle state
  + no tab entry
  + strongest resource release
  + simplest mental model
  - next call pays full cold creation/navigation cost

discard:
  + may retain some browser/tab lifecycle state
  + possible cheaper recovery
  - tab remains present
  - next use still requires page reload
  - larger lifecycle state space
```

### DECISION — initial production disposal

```text
CLOSE   = production v1 disposal strategy
DISCARD = characterization/benchmark candidate
```

The project should measure:

- memory after idle transition;
- CPU after idle transition;
- next-turn cold/warm latency;
- navigation cost;
- extension reconciliation complexity;
- foreground activation risk;
- stale tab identity behavior.

If DISCARD later demonstrates a meaningful advantage without compromising clarity or reliability, it can graduate through a separate evidence-backed decision.

---

# Part II — Temporary Chat as an HDE primitive

## 9. Why Temporary Chat matters for HDE

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
      Temporary Chat product semantics
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

## 10. Temporary Chat must be characterized, not assumed

The current product capability is intentionally `UNKNOWN`.

PR8.7 should therefore begin as a live characterization PR.

Desired properties to verify include:

```text
T0   product Temporary mode can be selected by the browser-owned runtime
T1   ordinary text turn succeeds under that mode
T2   authoritative response observation is available
T3   terminal/finality semantics can be proven somehow
T4   the resulting turn does not become an ordinary persistent-history conversation
T5   no accidental normal-chat fallback occurs when Temporary mode selection fails
T6   continuation semantics are explicitly characterized rather than assumed
T7   provenance records requested/selected/observed conversation mode
T8   capability changes UNKNOWN -> AVAILABLE only after live evidence
T9   identity semantics are characterized
T10  read/status/attach support or absence is characterized
T11  tab/browser restart persistence behavior is characterized
T12  Temporary -> Normal transition does not leak Temporary state
T13  Normal -> Temporary transition does not inherit durable mode accidentally
```

If product semantics differ from these expectations, the capability model should record the actual behavior rather than force the desired abstraction.

Fail-closed rule:

> If the caller explicitly requests Temporary Chat and the transport cannot prove that Temporary mode was selected before the write, it must fail before the write rather than silently creating a normal durable chat.

---

## 11. Temporary identity, persistence, and readback are first-class unknowns

A crucial review correction is that Temporary Chat must **not** be assumed to expose the same durable identity/readback contract as a normal conversation.

PR8.7 must explicitly answer:

```text
Does a temporary turn receive a conversation_id?
Is that ID stable for the turn?
Is it stable across multiple temporary turns, if continuation exists?
Is it visible to get_messages()?
Is it visible to get_status()?
Can attach_conversation() operate on it?
Does the identity disappear from ordinary history enumeration?
Does the turn survive runtime-tab recreation?
Does it survive browser restart?
Does it survive local process restart?
What exactly is the authoritative completion source?
```

Possible outcomes include:

### Outcome A — normal-like transient identity

```text
temporary conversation has an ID
canonical read/status can observe it
ordinary history does not retain/display it
```

This would compose naturally with the current canonical plane.

### Outcome B — ephemeral identity with partial canonical support

```text
turn has some product identity
but attach/read/status semantics differ
```

Then the runtime should model those differences explicitly.

### Outcome C — page-local/transport-local temporary lifecycle

```text
ordinary canonical conversation APIs cannot authoritatively observe the temporary turn
```

Then PR8.7 must **not** fabricate a normal durable-conversation contract merely for API uniformity.

The generic product runtime may need an explicit persistence dimension such as:

```text
ConversationPersistence.DURABLE
ConversationPersistence.EPHEMERAL
```

with optional/conditional identity fields.

### Core rule

> Ephemeral product semantics outrank API neatness. Do not invent durable identity just to make Temporary Chat look like a normal `ChatConversation`.

---

## 12. Temporary availability requires a transition matrix, not one successful turn

A single successful Temporary Chat is insufficient evidence for `AVAILABLE`.

Minimum live matrix should include:

```text
cold/no-runtime-tab Temporary turn
warm/reused-runtime-tab Temporary turn
Temporary -> Normal next turn
Normal -> Temporary next turn
Temporary with runtime-tab recreation
Temporary with explicit mode-selection failure
history/persistence observation
identity/readback/finality characterization
```

Especially important:

```text
TEMP -> NORMAL
NORMAL -> TEMP
```

These catch sticky product/UI mode contamination.

The runtime must not let a previous Temporary selection silently contaminate a later normal request, or vice versa.

---

## 13. Conversation-mode API direction

### DECISION

The primary public abstraction should be a conversation-mode request, not only a dedicated method.

Conceptual direction:

```python
runtime.send(
    prompt,
    conversation_mode="temporary",
)
```

A later convenience wrapper is acceptable:

```python
runtime.send_temporary(prompt)
```

but it should delegate to the same underlying mode contract rather than create a parallel implementation.

Provenance should expose at least:

```text
requested_conversation_mode
selected_product_mode
observed_conversation_mode
persistence_semantics
mode_selection_proven
```

---

## 14. Temporary Chat and browser lifetime naturally compose, but finality semantics come first

The intended one-shot HDE primitive eventually becomes something like:

```python
runtime.send(
    internal_prompt,
    conversation_mode="temporary",
    model_profile="fast",
    runtime_tab_policy="turn-scoped",
    runtime_tab_ttl=0,
    on_text_event=...,
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
revision-safe response observation
        |
        +--> browser authority released as soon as safe
        |
        v
terminal/finality semantics proven
        |
        v
no long-lived browser cost
```

If Temporary Chat requires the page until terminal completion, the Browser Authority Lease remains held until that point.

If not, `TURN_SCOPED + ttl=0` may release the heavy page earlier while the Turn Lifecycle Lease continues through an independent observation channel.

That is the ideal internal inference substrate for HDE while preserving ordinary ChatGPT product ownership of the write.

---

# Part III — Revision-safe streaming and perceived latency

## 15. The current latency problem is architectural, not imagined

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

## 16. Streaming means incremental text observation, not necessarily model tokens

The architecture review deliberately removes a token-centric assumption.

A product observation source may expose:

- append-only text deltas;
- complete growing snapshots;
- replacement/revision snapshots;
- structured content blocks;
- transient thinking/placeholder state;
- final canonical text.

Therefore the primary new contract should not promise true token boundaries unless they are actually observed.

### DECISION — primary streaming abstraction

Use revision-safe text events/snapshots as the canonical abstraction.

Conceptual event family:

```text
AssistantTextSnapshot
AssistantTextDelta
AssistantTextRevision
CanonicalTextFinalized
```

or an equivalent structured `TextObservationEvent` model.

Example:

```text
rev 1 snapshot: "The answer is"
rev 2 snapshot: "The answer is probably"
rev 3 snapshot: "The answer is definitely"
```

The runtime must not blindly emit:

```text
"The answer is"
" probably"
" definitely"
```

if the source actually replaced previous text.

`on_token` may remain as:

- a compatibility callback;
- an append-only helper when the chosen observation channel proves append-only behavior;
- a final full-text callback for legacy behavior until PR8.9 graduates.

It should not define the generic future streaming semantics.

---

## 17. Desired response lifecycle

The runtime should expose a turn as independently meaningful stages:

```text
T0  request accepted by local runtime
T1  browser write delegated
T2  product write accepted/observed
T3  first assistant text observation
T4  additional text deltas/snapshots/revisions
T5  last pre-final text observation
T6  canonical finality proven
T7  final stream/canonical reconciliation complete
T8  Turn Lifecycle Lease released
```

Browser Authority Lease release may occur at T2, T3, T4, T5, T6, or later depending on what live evidence proves.

HDE should be able to render from `T3` onward.

A successful final `ChatResponse` remains authoritative only after canonical/terminal completion semantics are proven.

Conceptual event flow:

```python
on_event(TurnStarted(...))
on_event(WriteAccepted(...))
on_text_event(AssistantTextSnapshot(...))
on_text_event(AssistantTextDelta(...))
on_text_event(AssistantTextRevision(...))
on_event(CanonicalCompletion(...))
on_event(StreamCanonicalReconciliation(...))
```

This preserves both goals:

```text
low perceived latency
+
strong canonical completion semantics
```

---

## 18. Streaming must not weaken finality governance

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
- reconcile using canonical/product state;
- preserve the partial observation in diagnostics/provenance where appropriate.

The existing no-automatic-retry invariant remains unchanged.

---

## 19. Stream-to-canonical reconciliation is mandatory

The user may have seen partial text that differs from the final canonical message.

The runtime must make that relationship explicit rather than assume identity.

Possible reconciliation states:

```text
EXACT_MATCH
    last streamed snapshot == canonical final text

CANONICAL_EXTENDS_STREAM
    stream ended before the final canonical suffix arrived

STREAM_REVISED_BY_CANONICAL
    canonical final text rewrote previously observed material

STREAM_INCOMPLETE
    partial observations existed but final comparison could not be completed

UNAVAILABLE
    no comparable canonical final text exists for this product mode
```

Suggested provenance:

```text
stream_observation_source
stream_revision_count
last_stream_text_digest
canonical_text_digest
stream_canonical_reconciliation
canonical_completion_proven
```

The full text need not always be duplicated in provenance if that would be wasteful; digests and structured observations may be sufficient.

### Core invariant

> Streamed text is provisional observation. Canonical/terminal product completion is authoritative when available.

---

## 20. Candidate streaming sources

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
assistant message exists and changes over time
   |
   v
emit revision-safe snapshots/deltas
```

If the canonical read surface exposes partial assistant text while generation is in progress, this is the preferred architecture.

Benefits:

- no extra DOM coupling;
- no rendered UI dependence;
- browser remains write authority only;
- same canonical plane already used for finality;
- HDE receives text without learning browser details.

Required correctness work:

- stable or explicitly changing message identity during generation;
- monotonic-text assumptions must be tested, not assumed;
- handle rewrites/replacements rather than only appends;
- avoid duplicate observation emission;
- distinguish temporary thinking/placeholder text from user-visible answer content if applicable;
- reconcile final canonical text against streamed observations.

### Candidate B — Safe browser network observation

If canonical reads do not expose useful partial text, the extension may observe the product response stream.

Important boundary:

```text
browser sees product response
       |
       v
extension emits only safe assistant text/event observations
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

### DECISION — PR8.9 source order

```text
1. incremental canonical observation
2. safe browser response observation
3. rendered page observation
```

PR8.9 should begin with a focused live characterization question:

> During generation, does the canonical message/read surface expose useful partial assistant content?

If the answer is clearly no, do not spend excessive time forcing Candidate A to work. Move to the next evidence-backed candidate.

---

## 21. Streaming and authority metrics should become first-class

PR8.9 should measure at least:

```text
local_request_start_ms
browser_write_accepted_ms
browser_authority_released_ms
first_text_observed_ms
last_text_observation_ms
canonical_completion_ms
response_returned_ms
```

Derived metrics:

```text
TTFW  = time to first write acceptance
TTFT  = time to first useful text observation
stream_duration
finality_lag = canonical_completion - last_text_observation
return_lag   = response_returned - canonical_completion
authority_release_lag = browser_authority_released - browser_write_accepted
```

If multiple observation channels are available, also measure:

```text
canonical_visibility_lag =
    first_canonical_partial_text - first_product_text_observed_elsewhere
```

The user-visible problem today is largely that `finality_lag + return_lag` is paid before any text is surfaced.

The goal is not necessarily to make canonical finality instantaneous. The goal is to stop blocking text presentation on finality when a safe partial observation already exists.

The authority metric answers a separate resource question:

> How long after write acceptance do we genuinely need to keep the heavy browser page alive?

---

# Part IV — Product model and reasoning selection

## 22. HDE needs fast and deep product modes

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

## 23. Prefer semantic model profiles over hard-coded product names

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

The mapping is product-specific and capability-observed.

An advanced exact selector may still be useful:

```python
model_exact="..."
```

but it should not be the only abstraction available to HDE.

---

## 24. Semantic model intent belongs in `ChatGPTProductRuntime`, above the concrete transport

### DECISION

HDE-facing semantic profiles should not be defined by the concrete browser transport.

Preferred ownership:

```text
HDE
 |
 v
ModelIntent(FAST / BALANCED / DEEP / MAX)
 |
 v
ChatGPTProductRuntime resolver
 |
 v
product-specific selector request
 |
 v
ProductWriteTransport applies/observes selector
```

The transport should expose what can be selected and what was observed.

The runtime should resolve semantic HDE intent into a product-specific request.

This preserves the ability to replace the browser-owned transport later without changing HDE policy vocabulary.

---

## 25. Model selection must be provenance-aware and strict when explicit

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

### DECISION — explicit selection is strict by default

```text
no explicit model intent
    -> ordinary inherited/default product behavior may be allowed

explicit model_profile/model_exact
    -> requested selection must be selected/proven before write
       or fail before write
```

Best-effort fallback is allowed only when the caller explicitly requests it.

Example:

```text
STRICT
  -> fail before write if requested mode cannot be selected/proven

BEST_EFFORT (explicit opt-in)
  -> continue if caller allowed fallback
  -> provenance records requested vs selected vs observed
```

Do not silently claim that the user requested a fast model when the page actually ran a deep reasoning mode.

---

## 26. Selection scope and sticky-state contamination must be characterized

Selecting a model/mode in a product UI may have state scope wider than one turn.

PR8.10 must explicitly determine whether selection affects:

```text
this turn only?
this conversation?
this runtime tab?
future new chats?
account/product default?
other manually open ChatGPT tabs?
```

The same concern applies to reasoning mode and conversation mode.

Critical transition tests include:

```text
FAST -> default/inherited
DEEP -> FAST
exact model A -> exact model B
Temporary + FAST -> Durable + default
Durable + DEEP -> Temporary + FAST
```

The runtime must prevent accidental sticky-state leakage between logically independent requests.

A later turn must not silently inherit Temporary or FAST merely because a prior turn selected it, unless the caller explicitly requested inherited behavior and provenance says so.

Suggested provenance:

```text
selection_request_source
selection_scope_observed
selection_before_write
selection_after_write
selection_inherited
selection_preserved
```

---

## 27. Capabilities need optional structured details for parameterized features

The four-state capability model remains correct:

```text
AVAILABLE
UNSUPPORTED
UNKNOWN
UNIMPLEMENTED
```

But a boolean-like state is not enough once a feature has sub-capabilities.

Example:

```text
model_selection = AVAILABLE
```

may still need to say:

```text
semantic_profiles = [FAST, DEEP]
exact_selection = UNKNOWN
reasoning_selection = AVAILABLE
strict_prewrite_verification = true
```

Likewise streaming may need:

```text
source = CANONICAL_INCREMENTAL
revision_safe = true
append_only = false
```

Temporary Chat may need:

```text
new_chat = AVAILABLE
continuation = UNKNOWN
canonical_read = AVAILABLE/UNKNOWN
history_persistence = EPHEMERAL
```

### DECISION — preserve the four-state model, extend descriptors

Do not replace PR8.5 capability states.

Instead allow optional structured feature details/evidence, for example conceptually:

```text
ProductCapability
    name
    state
    owner
    evidence
    details?   # structured, capability-specific
```

or an equivalent companion descriptor model.

Exact schema design belongs in the implementation PR that first needs it.

---

## 28. Temporary + FAST + streaming + bounded browser authority is the key HDE internal path

The features together are much more valuable than each feature independently.

```text
Temporary Chat
   +
FAST model profile
   +
revision-safe streaming
   +
TURN_SCOPED browser authority
```

creates an HDE primitive with desired properties:

```text
low first-text latency
no durable ChatGPT history clutter
minimal browser lifetime
explicit terminal/completion evidence
HDE-owned memory/context policy
```

This should be treated as a first-class product target, not an accidental combination of flags.

---

# Part V — Browser authority cost and debugger ownership

## 29. The debugger warning should not be “hidden” by bypassing browser UX

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

## 30. Candidate lower-authority browser path

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

### DECISION — debugger work sequence

```text
1. measure current attach/detach lifetime
2. shorten attachment window without changing semantics
3. verify live reliability
4. investigate debugger-free path separately
```

Do not combine “remove debugger” and unrelated product feature work into one unbounded rewrite.

---

## 31. Browser page cost should be measured before optimization

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

The invariant is:

> Do not break or approximate product semantics merely to make the page lighter.

---

## 32. A minimum resource baseline belongs in PR8.8; deep browser cost work belongs in PR8.11

The architecture review splits resource measurements into two levels.

### PR8.8 minimum lifecycle baseline

Needed before choosing lifecycle defaults:

```text
cold-start wall time
warm-reuse wall time
idle CPU
idle memory
close -> next-turn latency
foreground disturbance
runtime-tab creation/reuse rate
browser-authority lease duration
```

Without these measurements, `IDLE_TTL` defaults would be guesswork.

### PR8.11 deep resource baseline

More detailed optimization work:

```text
cold boot CPU time
network bytes transferred
request count
JS heap if available
DOM node count if available
GPU/compositor activity if measurable
per-turn CPU
per-turn network overhead
navigation/reload cost
debugger attach lifetime
resource-class contribution
```

Then experiments can remove or suspend resource classes one at a time.

---

## 33. The ideal browser lifecycle

The long-term browser-side state machine is approximately:

```text
ABSENT
  |
  | Browser Authority Lease acquisition
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
BROWSER-REQUIRED OBSERVATION / HANDOFF
  |
  v
AUTHORITY RELEASABLE
  |
  | release Browser Authority Lease
  v
QUIESCENT
  |
  | TTL
  v
DISPOSED
```

The Turn Lifecycle state machine may continue independently:

```text
TURN ACTIVE
  |
  v
PARTIAL OBSERVATION
  |
  v
CANONICAL / PRODUCT TERMINAL STATE
  |
  v
RECONCILIATION
  |
  v
TURN TERMINAL
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

## 34. Evidence correction: foreground activation is not a guaranteed invariant

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

## 35. The current manual research loop is already an algorithm

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

## 36. `chatgpt-web-adapter` should expose primitives; HDE should own research policy

It is tempting to put the entire research agent inside `chatgpt-web-adapter` because the repository already owns ChatGPT conversation access.

The better boundary is:

### Adapter responsibility

```text
send
revision-safe stream/text observation
status
messages
attach
Temporary Chat
model/reasoning selection
Browser Authority Lease / TTL
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

## 37. Temporary planner pattern

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

The planner does not need to pollute ChatGPT history. It may be a perfect `Temporary Chat + FAST + TURN_SCOPED` consumer.

The planner/evaluator should not be described as an **independent** evaluator merely because it uses a second turn. If it shares the same model/product family, it is a second-pass evaluator, not necessarily independent evidence.

---

## 38. Research controller should be more than automatic “continue”

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
    wait for canonical/terminal finality

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

## 39. Automation lineage and guards are required from the first version

Even a simple continuation controller should not run without bounded policy and durable step identity.

Minimum lineage:

```text
job_id
step_id
parent_step_id
attempt_id where needed
conversation_id / ephemeral identity when available
request fingerprint
canonical/terminal result identity
```

This lets crash recovery answer:

```text
Was step 17 planned?
Was it already sent?
Was write outcome ambiguous?
Was canonical completion proven?
May step 18 be created safely?
```

Minimum guards:

```text
explicit research goal
max_turns
max_runtime
max_failures
max_consecutive_low-value_turns
no automatic resend after ambiguous write
duplicate-turn fingerprint / similarity check
persistent job journal
explicit DONE state
explicit ABSTAIN / NEEDS_REVIEW state
human gate for tool/external actions
stop when planner cannot produce a policy-valid next action
stop when evaluator explicitly abstains
stop when required evidence is missing
stop on repeated contradiction/no-progress
```

The architecture review intentionally avoids making an uncalibrated self-reported “planner uncertainty threshold” a foundational safety guard.

If calibrated uncertainty evidence is introduced later, it may become an additional signal.

A useful mental model is not “fully autonomous agent.”

It is:

> A bounded research loop that removes repetitive monitoring and obvious continuation work while preserving clear stop, review, lineage, and failure boundaries.

---

# Part VII — Reviewed implementation sequence

## 40. PR8.7 — Temporary Chat Product Semantics, Ephemeral Identity / Persistence Characterization and Fail-Closed Conversation-Mode Governance

### Goal

Make Temporary Chat a proven product-runtime capability suitable for ephemeral HDE calls without pretending it has durable-conversation semantics that have not been demonstrated.

### Work

- characterize actual product Temporary Chat selection through the browser-owned transport;
- define explicit conversation-mode request;
- prove no silent durable-chat fallback;
- characterize new-chat/continuation behavior;
- characterize identity, persistence, read/status/attach and terminal semantics;
- characterize cold/warm and TEMP↔NORMAL transitions;
- preserve authoritative completion/readback where the product exposes it;
- add conversation-mode/persistence provenance;
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

### Architecture invalidation check

If Temporary Chat cannot be represented safely through the current product-runtime/canonical boundaries without major special-case coupling, stop and consider an early PR9.0 architecture checkpoint rather than forcing the abstraction.

---

## 41. PR8.8 — Browser Authority Lease, Turn Lifecycle Separation, Idle-TTL / Turn-Scoped Disposal and Cold/Warm Lifecycle Governance

### Goal

Stop treating the reusable runtime tab as an immortal resource and formally separate logical turn lifetime from browser-authority lifetime.

### Work

- explicit Turn Lifecycle Lease and Browser Authority Lease semantics;
- explicit lifecycle policy;
- `PERSISTENT`, `IDLE_TTL`, and `TURN_SCOPED` semantics;
- `PERSISTENT` remains initial compatibility default;
- per-turn/runtime/transport lifecycle precedence;
- TTL begins only after Browser Authority Lease release;
- lease/disposal fencing;
- no disposal while browser authority is still required;
- `TURN_SCOPED + ttl=0` for any evidence-backed safe turn;
- CLOSE as production v1 disposal;
- DISCARD characterization/benchmark only;
- cold/warm creation/reuse observations;
- minimum CPU/RAM/latency resource baseline;
- foreground disturbance metrics;
- safe recovery when the user manually closes the runtime tab.

### Core invariant

```text
no browser disposal before browser authority is proven unnecessary
```

This is deliberately different from:

```text
no browser disposal before canonical finality
```

because the latter may be unnecessarily conservative if future evidence proves early authority release safe.

### Architecture invalidation check

If page authority demonstrably cannot be separated from the full logical turn lifecycle, record that as a hard boundary for PR9.0 rather than hiding it behind timer policy.

---

## 42. PR8.9 — Incremental Text Observation, Revision-Safe Streaming, First-Delta Latency and Canonical-Finality Reconciliation

### Goal

Make HDE receive useful text as soon as it exists instead of waiting for the final-message polling loop.

### Work

- begin with focused incremental-canonical-read characterization;
- prove the best partial-text observation source;
- expose revision-safe text snapshots/deltas/revisions;
- retain `on_token` only as compatibility/helper semantics where justified;
- keep final canonical/product terminal response authoritative;
- measure TTFT, finality lag and browser-authority release lag;
- detect duplicate/rewritten partial text safely;
- reconcile streamed text with final canonical text;
- add explicit reconciliation result provenance;
- do not weaken ambiguous-write handling;
- capability changes `streaming: UNKNOWN -> AVAILABLE` only after live evidence.

### Core invariant

```text
partial text may be shown early
completion is not claimed until authoritative terminal semantics are proven
stream observations are reconciled with final product state when possible
```

### Architecture invalidation check

If low-latency streaming fundamentally requires a browser-ownership model incompatible with the current runtime seams, PR9.0 may move forward early before adding model/resource features on top of a boundary we intend to replace.

---

## 43. PR8.10 — Product Model / Reasoning Selection, Semantic Model Profiles, State-Scope Isolation and Selection Provenance

### Goal

Allow HDE to deliberately choose low-latency versus deep-reasoning product behavior without sticky state or silent model drift.

### Work

- characterize current product model/reasoning selector surface;
- semantic profiles such as `FAST`, `BALANCED`, `DEEP`, `MAX` at runtime level;
- optional exact model/mode escape hatch;
- strict-by-default explicit selection;
- explicit best-effort fallback only when caller opts in;
- requested/selected/observed model provenance;
- selection-preservation verification;
- characterize selection scope across turn/conversation/tab/account;
- add transition tests to catch sticky state;
- no silent drift from requested mode;
- introduce structured capability details if needed;
- capability updates only for proven selection/preservation behavior.

### Core invariant

```text
requested model intent must never be silently represented as honored when evidence says otherwise
```

### Architecture invalidation check

If reliable model selection requires a fundamentally different page-control/transport mechanism, record that boundary before continuing into PR8.11.

---

## 44. PR8.11 — Browser Authority Cost Reduction, Debugger Attachment Minimization and Deep Resource Baseline

### Goal

Reduce browser overhead and browser-visible authority while preserving product semantics.

### Work

- consume PR8.8 minimum lifecycle measurements rather than re-measuring blindly;
- deep cold/warm CPU, RAM, network and page-init baseline;
- idle resource baseline;
- attach/detach lifetime measurement for `chrome.debugger`;
- minimize debugger attachment duration where safe;
- independently investigate content-script / `chrome.scripting` alternative;
- investigate page-resource reduction only with evidence;
- benchmark DISCARD only if still justified;
- quantify cold-start foreground disturbance;
- characterize whether any lower-authority mechanism can replace CDP without changing product semantics.

### Explicit non-goal

Do not attempt to conceal or bypass Chrome security UI while continuing to use debugger authority.

The desired outcome is to remove/minimize the authority, not hide its indication.

### Architecture invalidation check

If a debugger-free/lower-authority approach is clearly superior but requires ownership changes larger than an incremental transport repair, defer the rewrite and carry the evidence into PR9.0.

---

## 45. PR9.0 — Next-Generation Product Bridge Architecture Feasibility

Normal sequencing places PR9.0 after PR8.7–PR8.11 provide real daily-use measurements.

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
Turn Lifecycle / Browser Authority separation
canonical-read independence
HDE coupling
first-text latency
finality lag
browser-authority release lag
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

## 46. Architecture Invalidation Check can move PR9.0 earlier

### DECISION

The normal order remains:

```text
PR8.7 -> PR8.8 -> PR8.9 -> PR8.10 -> PR8.11 -> PR9.0
```

But every PR8.7–PR8.11 closes with:

```text
ARCHITECTURE_INVALIDATION_CHECK
```

Ask:

```text
Did this PR reveal that the current product-runtime boundary cannot safely express the feature?
Did it reveal unavoidable browser coupling that invalidates the current ownership model?
Did it reveal that a next-generation bridge would materially change the implementation we are about to build next?
```

If yes:

```text
current PR evidence
      |
      v
FUNDAMENTAL_BOUNDARY_DISCOVERED
      |
      v
move PR9.0 forward
```

Do not mechanically execute PR8.10/PR8.11 on top of an architecture that earlier evidence has already invalidated.

---

# Part VIII — HDE integration strategy during this work

## 47. Do not wait for PR9.0 to start HDE integration

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
    # render revision-safe observations incrementally
    ...

if caps.state("model_selection") == "AVAILABLE":
    # apply HDE semantic model intent
    ...
```

HDE should not import browser-native implementation modules to gain these features.

---

## 48. Suggested HDE call classes

Eventually HDE may distinguish calls approximately like this:

### User-visible durable conversation

```text
mode: durable
model: FAST/BALANCED by default
streaming: yes
browser policy: moderate idle TTL after proven safe release
```

### Internal short inference

```text
mode: temporary
model: FAST
streaming: optional but preferred
browser policy: TURN_SCOPED, ttl=0 if proven safe
```

### Deep research step

```text
mode: durable research conversation
model: DEEP/MAX
streaming: yes
browser policy: long enough to preserve warm research session
```

### Planner/evaluator call

```text
mode: temporary
model: FAST
streaming: usually not required for UI, but useful for latency
browser policy: TURN_SCOPED, ttl=0 if proven safe
```

This keeps HDE policy readable while allowing the underlying transport to evolve.

---

# Part IX — Long-term north star

## 49. The end-state mental model

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
               revision-safe streaming
                          |
                  canonical finality
```

Browser authority is a separate replaceable component:

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
network plane          only while required
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

## 50. What belongs in `chatgpt-web-adapter`

The project should continue growing in the direction of **transport and product-runtime primitives**:

```text
health
capabilities
send
revision-safe text observation
status
messages
attach
Temporary Chat
model/reasoning selection
conversation mode provenance
completion provenance
Turn Lifecycle Lease / Browser Authority Lease semantics
runtime-tab TTL/reconciliation
browser-resource observations
```

These belong here because they describe how a local application safely and efficiently uses the ChatGPT product.

---

## 51. What should remain above the adapter

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

## 52. Practical vision

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
answer begins appearing almost immediately
            |
            v
HDE UI consumes revision-safe partial observations
            |
            +--> browser authority released when evidence permits
            |
            v
canonical/terminal finality proven
            |
            v
Temporary FAST planner proposes obvious next step
            |
            v
policy checks lineage / budget / duplication / stop conditions
            |
            v
next instruction is sent automatically
            |
            v
repeat until completion or review checkpoint
```

The user should no longer need to continuously monitor a ChatGPT tab merely to see whether the model has finished and type an obvious “continue.”

At the same time, the system should remain auditable, bounded, and explicit about:

- what was requested;
- what product mode was used;
- what text was provisional;
- whether revisions occurred;
- when canonical/terminal completion was proven;
- when browser authority became unnecessary;
- why an automated continuation was allowed;
- what job/step lineage produced it.

---

# Part X — Architecture-review resolutions

## 53. Resolved review questions

The full design review produced the following decisions.

### Q1 — Should `IDLE_TTL` become default immediately?

```text
DECISION: NO
```

PR8.8 keeps `PERSISTENT` as the compatibility default initially. `IDLE_TTL` is opt-in until measurements justify changing the daily-use default.

### Q2 — Should `ttl=0` be Temporary-only?

```text
DECISION: NO
```

Allow `ttl=0` for any explicit `TURN_SCOPED` call whose browser-authority release point is proven safe.

### Q3 — Close or discard?

```text
DECISION: CLOSE for production v1
DECISION_PENDING: DISCARD graduation
```

Benchmark DISCARD; do not expand production lifecycle state unless it demonstrates material value.

### Q4 — Evidence for `temporary_chat = AVAILABLE`?

Require:

```text
mode proven before write
successful product turn
no durable fallback
identity/persistence characterization
terminal/readback characterization
cold + warm cases
TEMP -> NORMAL isolation
NORMAL -> TEMP isolation
runtime-tab recreation behavior
```

### Q5 — Conversation mode or dedicated method?

```text
DECISION: conversation_mode is the primary abstraction
```

A dedicated helper may exist as a thin convenience wrapper.

### Q6 — Streaming source order?

```text
1 canonical incremental observation
2 safe browser response observation
3 rendered page observation
```

### Q7 — Token callbacks or another representation?

```text
DECISION: revision-safe text events/snapshots are primary
```

`on_token` remains compatibility/helper behavior where justified.

### Q8 — Stream/final consistency contract?

```text
DECISION: streamed text is provisional; authoritative terminal text wins
```

Expose explicit reconciliation state.

### Q9 — Where do semantic model profiles live?

```text
DECISION: ChatGPTProductRuntime layer
```

The concrete transport applies/observes product-specific selectors.

### Q10 — Strict model selection behavior?

```text
DECISION: explicit selection is strict by default
```

Best-effort fallback requires explicit caller opt-in.

### Q11 — Debugger minimization strategy?

```text
measure -> shorten attachment -> verify -> investigate debugger-free path
```

Do not hide browser security UX.

### Q12 — Resource metrics before optimization?

Minimum PR8.8 metrics:

```text
cold/warm latency
idle CPU/RAM
close -> next-turn latency
foreground disturbance
browser-authority lease duration
```

Deep PR8.11 diagnostics add network/DOM/heap/GPU/debugger/resource-class analysis.

### Q13 — Where should HDE Research Runner live?

```text
DECISION: HDE-side, not chatgpt-web-adapter
```

Start near HDE runtime/session orchestration; physically extract later only if it becomes a standalone subsystem.

### Q14 — Minimum automation guards?

Require:

```text
explicit goal
job/step lineage
turn/time/failure budgets
duplicate detection
persistent journal
DONE/ABSTAIN/REVIEW states
no resend after ambiguous write
human gate for external effects
no-progress stop policy
```

### Q15 — Should PR9.0 move earlier?

```text
DECISION: normal order remains after PR8.11
```

But every preceding PR has an Architecture Invalidation Check and may advance PR9.0 if a fundamental boundary is discovered.

---

## 54. Remaining deliberately open questions

The review resolves architecture policy, but live product behavior still owns several answers:

```text
Does Temporary Chat expose normal-like canonical identity?
Can browser authority be released before canonical finality?
Does canonical read expose useful partial text during generation?
How often does partial text revise rather than append?
What exact scope does product model selection mutate?
Can content-script interaction preserve current write semantics?
Does DISCARD materially outperform CLOSE?
What TTL gives the best daily-use cold/warm/resource tradeoff?
```

These are not documentation gaps. They are explicit experiment questions for PR8.7–PR8.11.

---

# 55. Proposed order

```text
PR8.6   Public-surface / compatibility boundary        COMPLETE
   |
   v
PR8.7   Temporary semantics + ephemeral identity/persistence
   |
   v
PR8.8   Browser Authority Lease + TTL / disposal
   |
   v
PR8.9   Revision-safe streaming + canonical reconciliation
   |
   v
PR8.10  Model/reasoning selection + state-scope isolation
   |
   v
PR8.11  Browser authority cost + debugger minimization
   |
   v
PR9.0   Next-generation bridge architecture decision
```

At each PR boundary:

```text
ARCHITECTURE_INVALIDATION_CHECK
```

HDE integration can proceed in parallel from the current PR8.6 baseline rather than waiting for the entire sequence.

A first HDE Research Runner can also begin in parallel once Temporary/streaming/model controls have enough evidence for the desired workflow.

---

# 56. Final statement

The long-term objective is no longer just:

> “Make ChatGPT callable from Python.”

The stronger objective is:

> Build a small local ChatGPT product bridge that lets HDE and other local tools use ordinary ChatGPT product semantics with low latency, explicit capability/provenance contracts, temporary or durable conversation modes, deliberate model selection, bounded browser authority, and a replaceable browser/write implementation.

The current browser-owned tab is the first proven authority mechanism behind that contract. It should not become the contract itself.

The intended daily-use experience is:

```text
idle:
    browser authority absent or nearly free

request:
    create/reuse authority
    acquire Browser Authority Lease
    perform page-owned write
    surface revision-safe text as soon as safely observed

browser lifecycle:
    release Browser Authority Lease as soon as product evidence permits
    apply configured TTL
    close when idle lifetime expires

turn lifecycle:
    retain Turn Lifecycle Lease through authoritative finality/reconciliation
    never resend automatically after an ambiguous write

Temporary one-shot:
    temporary mode proven before write
    fast model intent proven before write when explicitly requested
    revision-safe stream
    terminal semantics
    TURN_SCOPED browser authority

research automation:
    durable main research chat
    temporary fast planner/evaluator
    job/step lineage
    bounded automatic continuation
    human review when policy requires it
```

The strongest reviewed architectural distinction is:

```text
Browser Authority Lease != Turn Lifecycle Lease
```

That distinction allows the project to pursue ultra-light browser ownership without sacrificing canonical correctness.

The second major distinction is:

```text
Incremental Text Observation != Canonical Finality
```

That distinction allows the project to pursue near-immediate perceived response latency without weakening completion governance.

The third is:

```text
chatgpt-web-adapter owns product-runtime primitives
HDE owns cognition, research policy, and workflow meaning
```

That boundary keeps the library useful even if PR9.0 eventually replaces the current browser-owned implementation.

This is the reviewed direction to preserve through PR8.7–PR9.0 implementation.