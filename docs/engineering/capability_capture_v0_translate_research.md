# Capability Capture v0 — Google Translate falsification, slice A

Status: **RESEARCH-ONLY / NON-EXECUTABLE**. Slice B one-demo structural
live gate: **PASS** (2026-10-08); Slice C generated replay: **NOT STARTED**. Baseline:
`main@02b56911ae132d91d35d8bb87511141351968f80`.

This is not a recorder, browser compiler, product write path, public API, generic
capability registry, or proof of generated browser replay. The first slice
converts a **human-annotated reference workflow** into an intentionally
non-executable `CandidateCapabilitySpec` and tests that it cannot silently
erase the proven product-specific safety distinctions.

## Why Google Translate first

PR16.2 already establishes a non-chat browser-owned `translate_text`
capability without conversation identity or canonical service readback.
Its exact current implementation is the reference, not a new guessed product
protocol. The experiment must not add direct private HTTP requests.

Source evidence:

- `src/chatgpt_web_adapter/google_translate_web.py`
- `src/chatgpt_web_adapter/browser_native_extension/service_worker_google_translate_capability.js`
- `docs/engineering/pr16_2_google_translate_non_chat_capability_spike.md`

## Reference semantics to preserve

```text
route_languages
  → clear_source
  → prove_result_cleared
  → mutate_source_input         # product effect may start here
  → observe_stable_result
  → verify_result_route
```

The effect boundary is **source input mutation**, not a submit click.
A lost completion signal after this point requires reconciliation and must
not trigger a second product mutation.

```text
inputs                 = text, source_language, target_language
result evidence        = PAGE_DOM_STABLE_TRANSLATION
canonical completion   = false
automatic retry        = false
result identity        = product-specific stable page result
```

The exact DOM selectors are product-local evidence, not universal locator
contracts. `PAGE_DOM_STABLE_TRANSLATION` must not be promoted to canonical
completion or durable result identity.

## Slice A implementation

`tools/capability_capture_v0.py`:

1. Requires the exact bounded phase annotation from the proven reference.
2. Produces an immutable candidate with an explicit input/effect/finality
   boundary and fail-ambiguous policy.
3. Marks the output `MANUAL_REFERENCE_ANNOTATION_NOT_CAPTURED` and
   `executable=false`.
4. Inspects an **already obtained** `GoogleTranslateTextResult` for
   compatibility. Inspection never calls the bridge or browser.
5. The CLI prints only a static structural candidate. It does not contain
   user text, credentials, DOM dumps, signed URLs or browser network payloads.

Offline inspection:

```powershell
python -m tools.capability_capture_v0
python -m pytest -q tests/test_capability_capture_v0.py
```

This validates **neither** automatic capture nor generated replay.

## Next slices and falsification gates

**B — bounded real capture (zero write in the capture infrastructure)**

Instrument a single user-directed demonstration in the authenticated browser,
recording only bounded structural/semantic events and observations: control
role/name (redacted/bounded), route identity, product-owned outcome assertions,
and before/after state. Never persist credentials, arbitrary page content,
raw request/response bodies or arbitrary user input. The recorder is
observational and cannot grant new mutation authority.

**C — browser replay candidate**

Compile captured evidence into a private browser-owned executor. Admit at most
one explicitly approved effect; do not delegate an ambiguous mutation twice.
A post-effect lost ACK must produce `RECONCILE_NO_AUTO_RETRY`.
Compare against a separately observed reference CWA run.

**D — independent cases**

Only after Translate survives do the same exercise with Notebook
`add_url_source` (persistent entity/finality) and ChatGPT ordinary text turn
(protected write + canonical readback). Both must expose cases the Translate
model cannot silently flatten.

## Decision metrics

| Metric | First criterion |
| --- | --- |
| Reproducible input binding | New text/language pair does not require editing locators |
| Equivalence | Same input/output semantics and evidence class as reference |
| Effect safety | Zero duplicate product mutations after ambiguous injected ACK |
| False completion | Zero canonical-complete claims for Translate |
| Capture privacy | Zero raw content/credential/network-body retention |
| Coverage | Later two materially different products preserve their own boundaries |
| Authoring cost | Measure human annotation/rework versus hand-written reference |

A spec that passes only slice A is **not** a reusable learned capability.
If slice B or C needs bespoke selectors/finality guesses or cannot reproduce
reference semantics, record a **failed or inconclusive experiment**; do not
introduce a generic `HostedCapabilityRuntime` for symmetry.

Ownership remains: CWA executes and proves; external agents/users own
goals, permission, and next-action policy.


## Slice B implementation — opt-in structural observer

The research branch now contains a candidate capture operation wired through the
existing Native Messaging authority lane. **It has not yet passed a real Chrome
demonstration**, and it is not a production feature.

```text
explicit human consent + exact tab id
→ existing translate.google.com tab with matching sl/tl
→ attach CDP debugger (no navigation or activation)
→ install bounded input-event counter
→ human types the demonstration
→ poll output DOM structural candidates
→ collect capped event timeline
→ remove listener and detach debugger
→ validate strict allowlisted evidence schema
```

**No product input is sent by the observer.** The human demonstrator
performs any hosted mutation knowingly; the observer merely watches.
The Chrome debugger may display its normal attachment notice. It must not
interfere with any concurrent CWA operation: the host's existing exclusive
authority lane rejects contention.

Only these fields are admitted by the client:

- fixed schema/product/mode identity;
- tab id and language codes (not complete URLs);
- zero-to-64 event count, maximum four fixed phase labels;
- bounded relative timestamps;
- boolean route match, candidate presence, structural candidate count result;
- explicit `semanticFinalityProven=false`, `canonicalCompletionProven=false`,
  `automaticRetry=false`, and `replayExecutable=false`.

No field value, translation text, page text, cookies, raw DOM, CDP network
body, signed URL or content-derived hash leaves the page. The script reads
source text only to reject a prefilled source at install time, and checks
translated output text only for **nonempty presence**. It does not compare
translation identity/contents, so stability of candidate presence is **not**
`PAGE_DOM_STABLE_TRANSLATION` finality.

### Local-only manual gate

Use a **research build** of the extension and Native Messaging host from
PR #201. The published `0.3.0` runtime and standard `main` build do not
have the research operation.

1. Open Google Translate in Chrome with the intended language pair encoded
   in the route; ensure the source field is **empty** **and the previous
   translated output is cleared**. The research observer refuses to arm if
   it detects an existing output candidate.
2. Find the exact tab id without reading its contents. In Chrome,
   open `chrome://extensions`, enable developer mode if necessary, locate the
   **research** CWA extension, and inspect its service worker. In that
   extension's DevTools Console run:

```javascript
chrome.tabs.query({ url: "https://translate.google.com/*" }).then((tabs) =>
  console.table(tabs.map((tab) => ({ id: tab.id, active: tab.active })))
);
```

   Choose the one Translate tab intended for the demonstration. This command
   reads only tab IDs and whether each is active; it does not activate tabs,
   perform an input write, or print full URLs or page contents. Close the
   extension DevTools before testing if it interferes with debugger attachment.
   Never guess the tab id or target other tabs.
3. Start capture with explicit consent, and then manually type a short,
   **non-sensitive** demonstration text in the selected Translate tab:

```powershell
python -m tools.capability_capture_v0_browser `
  --tab-id <EXACT_TRANSLATE_TAB_ID> `
  --source-language en `
  --target-language es `
  --seconds 12 `
  --i-consent-to-structural-capture
```

4. A success status means only that an observational trace passed the strict
   schema; it is **not** permission to replay or retry product writes.
5. Independently obtain the existing hand-written CWA
   `GoogleTranslateTextResult` from an intentionally separate, bounded
   reference invocation when appropriate. Do not auto-write during capture.
6. Record whether the candidate trace contains
   `source_input_event → result_candidate_seen → result_candidate_presence_stable`
   while preserving `semanticFinalityProven=false`.

Suggested bounded offline gates:

```powershell
python -m pytest -q tests/test_capability_capture_v0.py tests/test_capability_capture_v0_browser.py
python -m ruff check tools/capability_capture_v0*.py tests/test_capability_capture_v0*.py
python -m ruff format --check tools/capability_capture_v0*.py tests/test_capability_capture_v0*.py
node --check src/chatgpt_web_adapter/browser_native_extension/service_worker_capability_capture_v0.js
node tools/capability_capture_v0_dom_fixture.js
```

### Empirical Slice B result — 2026-10-08

The first authenticated/local Chrome observation completed without transport
error but began too late to meet the stability window:

```text
source_input_event       18,061 ms
result_candidate_seen    19,617 ms
capture deadline         20,000 ms
candidatePresenceStable  false
```

The second explicit-consent observation on exact research head
`eb8e1b9d51a48369fd4f06e5bc8f8b0930ee146c` produced:

```text
source_ready                     0 ms
source_input_event               2,948 ms
inputEventCount                  5
result_candidate_seen            4,336 ms
result_candidate_presence_stable 5,567 ms
routeVerified                    true
candidatePresenceStable          true
candidateIdentityResolved        true
semanticFinalityProven           false
canonicalCompletionProven        false
automaticRetry                   false
replayExecutable                 false
rawContentRetained               false
```

Source: a sanitized output reported by the human operator from a local
Google Translate `en → es` demo using the research extension. This is
**empirical, single-run evidence**, not CI or a synthetic fixture. The
exact research commit passed CI #1976 (16/16 jobs).

**Verdict:** the first single-demonstration **structural observer** acceptance
gate is now **PASS**. Chrome accepted the opt-in capture, human input was
observed, the output candidate appeared, and presence stability was observed.

The evidence scope is deliberately narrower than `translate_text`
success. Capture did not observe the actual requested source content,
translation text equality, or textual stability; its
`candidateIdentityResolved` indicates stable structural candidate presence
only. By design `semanticFinalityProven=false`, so no captured trace becomes
authorization for replay, retry, or canonical completion.

A success-shaped returned capture implies the code's detach/observer
cleanup did not signal failure, but it is not independent proof of cleanup
across browser versions. Do not generalize the one live case.

### Evidence boundary and explicit incompleteness

A clean offline CI proves static input validation, response admission and
synthetic DOM evidence only. It cannot prove that the current live Google
Translate UI exposes compatible selectors or that attaching CDP while the
user types is reliable on all browser versions.

The specific one-demonstration **structural observation** gate is now closed
by the 2026-10-08 result above. This does not close live semantic-finality
proof or future cross-version observer robustness. A future failed capture is
an experimental result; do not silently switch transports, infer finality or
automatically repeat the user action.

### Slice C preflight — offline replay admission, no mutation

The added `tools/capability_capture_v0_gap_audit.py` accepts a **saved,
sanitized structural trace** and prints a machine-readable admission verdict.
It does not connect to Chrome, infer raw text, execute a product write or
promote any capability to executable. Expected source and target language
codes are supplied **independently** of the saved trace to avoid circular
acceptance of tampered language identity:

```powershell
python -m tools.capability_capture_v0_gap_audit .\\trace.json `
  --source-language en `
  --target-language es
```

A structural trace like the second 2026-10-08 live result must classify as
`STRUCTURAL_DEMONSTRATION_ACCEPTED`, but always report
`replay_executable=false` and `write_authority_granted=false`. A short,
unstable trace classifies as `OBSERVATION_INCOMPLETE`.

Both cases explicitly leave these gaps:

```text
capture_bound_to_exact_source_text
translation_text_identity_proven
translation_text_stability_proven
generated_locator_replay_proven
explicit_replay_write_authority
post_effect_lost_ack_reconciliation_proven
```

Those requirements are not inferred from a valid trace's status flags or
from the manually annotated candidate spec. The offline gap audit's
role is to *stop* premature compilation/replay, not to pass it.

### Slice C0 — semantic plan compiler (offline, not a replay executor)

`tools/capability_capture_v0_semantic_plan.py` accepts an admitted
structural trace and **independently specified** language expectations. It
joins the trace with the explicitly hand-written PR16.2 Translate reference
annotation to produce a small, non-executable semantic plan.

```powershell
python -m tools.capability_capture_v0_semantic_plan .\\trace.json `
  --source-language en `
  --target-language es
```

The plan gives each reference phase its own provenance:
`CAPTURE_OBSERVED_ROUTE_ONLY`, `CAPTURE_OBSERVED_HUMAN_INPUT_EVENT_ONLY`,
`CAPTURE_OBSERVED_STRUCTURAL_PRESENCE_ONLY`, or
`HANDWRITTEN_REFERENCE_ONLY`. It does **not** treat the first seen event as
a uniquely identified DOM input, or presence stability as translated-text
stability.

The two preliminary locator templates are explicitly
`HANDWRITTEN_REFERENCE_HEURISTIC_NOT_CAPTURED`: a visible enabled textbox
candidate and a visible result-leaf candidate. **Neither template is a
learned locator.** Their product-specific grouping was supplied by the
existing reference, not derived from the four emitted live event labels.

`evaluate_locator_fixture(...)` is a pure, bounded synthetic DOM-descriptor
evaluator, not a CDP command. It counts exact role/family matches. Zero yields
`MISSING`, one yields `UNIQUE_IN_SYNTHETIC_FIXTURE`, two or more yields
`AMBIGUOUS`; ordering and a `leftmost` fallback never grant authority.
Even a unique synthetic fixture does not prove live locator identity.

The plan always contains:

```text
input.value_captured            false
locator_identity_proven         false
required_finality_proven        false
new_write_authority             false
automatic_retry                 false
executable                      false
promotion_verdict               BLOCKED_UNPROVEN_SEMANTICS_AND_AUTHORITY
```

It cannot issue a browser command, bind a source-text value, navigate,
reconcile a product write, or decide to repeat a mutation. This intentionally
tests the **gap** between observed trace and an executable API, not a
premature positive replay proof.

Offline targeted checks:

```powershell
python -m pytest -q tests/test_capability_capture_v0_semantic_plan.py
python -m ruff check tools/capability_capture_v0_semantic_plan.py tests/test_capability_capture_v0_semantic_plan.py
python -m ruff format --check tools/capability_capture_v0_semantic_plan.py tests/test_capability_capture_v0_semantic_plan.py
```

**Slice C1 future evidence gate:** capture sufficiently discriminating
source/result semantic attributes under explicit privacy constraints;
prove locator uniqueness across a fresh renderer and at least one UI
variation; explicitly authorize exactly one effect; inject post-effect lost
ACK and require reconciliation/no automatic retry; compare the product-owned
semantic result against the existing handwritten `translate_text`
reference. The Slice B trace alone is insufficient for all of these.

### Slice C1 — read-only two-document semantic locator characterization

The research branch now offers **a separate, explicitly consented C1 operation**
`research_capture_translate_semantic_v0`. It does not replay the demonstration.

Protocol:

```text
explicit, distinct Chrome tab IDs A/B + independently supplied sl/tl
→ verify exact Google Translate origin and route per tab
→ sequential CDP read-only Runtime.evaluate snapshots
→ count visible eligible source candidates and visible result-leaf candidates
→ export a descriptor only when its reference family has exactly one candidate
→ detach debugger from A before attaching to B
→ compare bounded descriptors (role/kind/coarse viewport region)
→ refuse to infer learned selectors, semantic finality, or write authority
```

The selector families are **handwritten Translate reference heuristics**:
`textarea` or `[contenteditable="true"][role="textbox"]` for source;
`[jsname="W297wb"], [jsname="jqKxS"]` for result leaves. They are not
derived from the Slice B timeline. C1 deliberately does not return those
selectors, DOM paths, element identifiers, accessible names, user input,
translated text, raw URLs, cookies, screenshots, DOM dumps, or network bodies.
Only counts up to 8 and closed-enum descriptors leave the page. Overflows
fail closed. Visibility/eligibility are checked inside the page but raw styles
and geometry are not exported.

The two observations are from **distinct explicitly selected Chrome tabs**,
which gives separate page documents; separate Chrome renderer OS processes
are not proven. We do not control site reload or claim fresh document
creation. A consistent, unique-in-family descriptor in both documents is
reported as `CONSISTENT_REFERENCE_FAMILY_SIGNATURE`, not an executable or
uniquely learned locator. Missing, multiple, unknown-region, or changed
signatures are reported without fallback to a leftmost control.

Local research-only trial, after installing the branch's research extension
and native host, opening **two distinct** Google Translate tabs with the same
exact `en → es` route, and looking up both exact tab IDs:

```powershell
python -m tools.capability_capture_v0_semantic_browser `
  --tab-id-a <FIRST_EXACT_TRANSLATE_TAB_ID> `
  --tab-id-b <SECOND_EXACT_TRANSLATE_TAB_ID> `
  --source-language en `
  --target-language es `
  --i-consent-to-semantic-observation
```

This command performs no product write, activation, navigation, reload, or
automatic retry. The result may legitimately be `MISSING` or `AMBIGUOUS`;
that is scientific evidence, not an error requiring heuristic fallback.
To test variation, use separately prepared tabs/layouts (for example, different
window sizes) in later controlled trials, recording only sanitized results.
Do not disturb a working CWA installation until the exact research CI is green.

Admissible response classes:

- `MISSING`: zero eligible nodes in either document
- `AMBIGUOUS`: more than one eligible node in either document
- `CHANGED_STRUCTURAL_SIGNATURE`: one per document, but enum signatures differ
- `UNRESOLVED_REGION`: viewport geometry is unavailable
- `CONSISTENT_REFERENCE_FAMILY_SIGNATURE`: one per document, same enum
  signature; **still not replay proof**

All results preserve `semantic_finality_proven=false`,
`replay_executable=false`, `new_write_authority=false`, and
`automatic_retry=false`. C1 success is **not** permission for Slice C2
product mutations. A separate explicit effect budget, source-text binding,
output-text stability and ambiguous-ACK reconciliation proof remain gates.

### C1 first live attempt — missing outer dispatch, repaired

The first two-tab local attempt (2026-10-08) produced
`BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION: timed out`.
This is **not** a measured DOM-locator failure or two-document verdict.
Inspection revealed that the existing outer Google Translate message handler
delegated only `research_capture_translate_demo_v0`; the new
`research_capture_translate_semantic_v0` message fell through to the
unrelated base handler rather than reaching the C1 dispatcher. This routing
bug is corrected within the research Translate domain; the frozen native
router remains unchanged. A synthetic test now explicitly executes both
outer branches and refuses fallthrough.

A second independent defect affected error classification: the old C1 local
RPC timeout was 20 seconds with only a two-second delegated-response margin,
whereas the native broker may wait the delegated timeout **plus five seconds**
before replying. The local socket could therefore expire before the broker
returned a useful `BROWSER_NATIVE_EXTENSION_TIMEOUT`. The research
client now reserves a ten-second response margin on a 30-second RPC
budget; it still makes a single, non-retried, read-only request.

**Live outcome remains UNPROVEN after repair** until a fresh research extension
reload and another explicit, consented C1 observation. Do not interpret the
original timeout as `MISSING` or `AMBIGUOUS`, nor silently retry it.

### C1 first successful two-tab transport — source stable, result missing

A human-operated live C1 run on 2026-10-08 returned a valid
`CWA_CAPTURE_C1_STRUCTURAL_COMPARISON` result after the routing repair:

```text
independent_documents_observed          true
source_input.status                    CONSISTENT_REFERENCE_FAMILY_SIGNATURE
source_input.same_signature            true
source_input.learned_locator_proven     false
translated_result.status               MISSING
translated_result.same_signature       false
translated_result.learned_locator      false
new_write_authority                    false
replay_executable                      false
semantic_finality_proven               false
```

**Verdict:** C1 transport and one live **source-input** signature comparison
pass, but the result slot remains unresolved. The comparison previously
discarded per-document counts; `MISSING` meant zero qualifying visible
reference-family result nodes in **at least one** of the two tabs, not
necessarily both. No conclusion about translation contents or selector drift
can be drawn from this aggregated output alone.

The offline Python comparison now retains already-validated bounded
`candidate_counts_by_document: {A: 0..8, B: 0..8}` for each slot. This
adds **no CDP operation**, no page-content read, no raw element metadata,
no navigation and no extension/native-host change. Its purpose is only to
tell which prepared page lacks matching candidates.

Next controlled observation: ensure both exact-route tabs visibly show
a harmless translated result from user-entered text, then run the existing
opt-in two-tab C1 command once. If both result counts are zero despite
visible translations, audit the hand-written reference-family selectors
separately; do not infer the answer or choose a different element by order.
If one count is zero, inspect that tab's visible state, not the other tab.
All replay/write permissions remain false.

### C1 reference-family selector-stage diagnostic — 2026-10-08

The second consented C1 live attempt, on
`3b2d2b3c2f1cef3d1df3acb5430e8065424bcd20`, returned source
`A=1, B=1` with matching signatures, but result `A=0, B=0`.
The operator had been asked to prepare translations in both tabs.
This is a **failure to detect visible result candidates within the
handwritten reference family**, not proof that translation text was absent.
The earlier manual demonstration had detected a result; the two observations
are not interchangeable because they may represent different page states.

The old C1 comparison made the following distinct causes indistinguishable:

- zero raw matches for `[jsname="W297wb"], [jsname="jqKxS"]`;
- matches present in the DOM but not qualifying as visible;
- visible matched candidates reduced to no leaf candidate.

C1 now emits only a capped three-stage count vector for each of the
already-authorized two page documents:

```text
resultFamilyStages.rawFamily      # raw selector-family matches, 0..8
resultFamilyStages.visibleFamily  # matched nodes qualifying as visible, 0..8
resultFamilyStages.visibleLeaves  # visible deepest matched descendants, 0..8
```

The Python comparison reports this as
`reference_family_stages_by_document.A/B` and derives a
`reference_family_diagnosis_by_document.A/B` with one of:

```text
NO_REFERENCE_SELECTOR_MATCH
SELECTOR_MATCHES_NOT_VISIBLE
VISIBLE_FAMILY_WITHOUT_LEAF
VISIBLE_REFERENCE_FAMILY_LEAF_PRESENT
```

This diagnostic extension upgrades the structural protocol to
`CWA_CAPTURE_C1_TWO_DOCUMENT_STRUCTURE_V2` and the comparison output to
`CWA_CAPTURE_C1_STRUCTURAL_COMPARISON_V2`; mixing old and new schemas
fails closed. Counts must be integral, bounded and monotonic:
`rawFamily >= visibleFamily >= visibleLeaves`, with the last exactly
equal to the candidate count already returned for `translated_result`.

**No selectors are learned or modified; no user text, DOM attributes,
network data, page URLs or custom geometry is exported.** Candidate
families are still inherited from the manual PR16.2 reference. This
does not establish result identity, textual stability, renderer process
independence, replay capability or new write authority.

A bounded real Chrome comparison after branch/extension sync determines
whether the next action should be a reference-selector audit, a visibility
audit, or a controlled observation of changed page state. Do not fix the
handwritten driver until that evidence is available.

### C1 completed bounded structural two-document gate — 2026-10-08

The third human-operated, consented, **read-only** C1 observation on exact
research head `ce51803ee601fcfdcf4da3b954cba0f0641aa41d` returned
`CWA_CAPTURE_C1_STRUCTURAL_COMPARISON_V2`:

```text
                                      document A        document B
source_input.candidateCount                     1                 1
translated_result.rawFamily                     2                 2
translated_result.visibleFamily                 2                 2
translated_result.visibleLeaves                 1                 1

source_input.status                CONSISTENT_REFERENCE_FAMILY_SIGNATURE
translated_result.status           CONSISTENT_REFERENCE_FAMILY_SIGNATURE
translated_result.diagnosis A/B     VISIBLE_REFERENCE_FAMILY_LEAF_PRESENT

independent_documents_observed     true
independent_renderer_process       false
selector_families_from_capture     false
learned_locator_proven             false (both slots)
semantic_finality_proven           false
replay_executable                  false
new_write_authority                false
automatic_retry                    false
```

The legacy `[jsname="W297wb"],[jsname="jqKxS"]` selector family matched
two visible nodes in **each** inspected document. Filtering out matched
ancestors yielded one structural leaf candidate per document. This
**falsifies the blanket hypothesis that the handwritten result selector
family is always absent on these pages**. It does not prove that that leaf
is semantically the translated output, that its text matches the requested
input, or that its identity will persist across UI revisions.

Earlier observations on the same day returned `translated_result: A=0,
B=0`, but only the new run measured selector-stage counts. Different
page states or sampling times can explain the difference; no causal
explanation is proven. Do not retrospectively assign the old zero-count
to selector absence, hidden elements, or stale Chrome state.

**Bounded gate verdict:**
`C1_REFERENCE_FAMILY_TWO_DOCUMENT_STRUCTURE_SUPPORTED`.
Two manually inherited source/result families have replicated structural
signatures in one pair of exact-route page documents. This is **not**
`C1_LEARNED_LOCATOR_SUPPORTED`, semantic finality, or authority to replay.

**Next discriminating study, not yet executed:** use an explicitly
human-driven crossed state contrast: (A empty, B showing benign translated
text), then reverse the states (A showing benign translation, B empty).
The read-only C1 observer must be run independently after each manual
preparation, with exact same routes and independently confirmed current
tab IDs. Count transitions correlated with the intended result state may
support attribution to *an output region*, but not translated-text
correctness or generalized locator learning. A state-insensitive outcome
requires investigating the family as possible UI decoration. Never write,
clear, or retry automatically; do not read/export page text. Treat any
mismatch as an experimental result.

### C1 completed crossed-state human demonstration — 2026-10-08

Two *separately invoked*, explicit-consent, read-only C1 V2 observations were
performed on the same two specified exact-route (`en → es`) Translate tabs,
with the operator **manually** swapping which page displayed a benign
translation. No CWA product writes, navigation, content export or retry
occurred during the C1 snapshots.

| Human-prepared state | A result raw/visible/leaves | B result raw/visible/leaves | Source A/B |
| --- | --- | --- | --- |
| A cleared, B translated (leg 1) | `0/0/0` | `2/2/1` | `1/1` |
| A translated, B cleared (leg 2) | `2/2/1` | `0/0/0` | `1/1` |

The explicit per-document V2 diagnoses invert along with the manually
prepared page states:

```text
Leg 1: A=NO_REFERENCE_SELECTOR_MATCH, B=VISIBLE_REFERENCE_FAMILY_LEAF_PRESENT
Leg 2: A=VISIBLE_REFERENCE_FAMILY_LEAF_PRESENT, B=NO_REFERENCE_SELECTOR_MATCH
```

Both outputs retained:

```text
independent_documents_observed      true
independent_renderer_process_proven false
selector_families_from_capture      false
learned_locator_proven              false
semantic_finality_proven            false
replay_executable                   false
new_write_authority                 false
automatic_retry                     false
```

**Verdict:**
`C1_REFERENCE_FAMILY_RESULT_STATE_ASSOCIATION_SUPPORTED_BY_CROSSOVER`.
This crossed pair supports the narrower claim that the **existing handwritten
result-family DOM footprint co-varies with the operator-described
empty/translated page state, in both directions and on both tabs**. It is
stronger than one observation because it rules out a static tab-A vs tab-B
difference as a sufficient explanation of these two cases.

It does not prove the leaf's text was a correct translation, isolate all other
changes caused by typing/clearing, rule out transient timing effects, establish
unique node identity across reloads, infer family selectors from the
demonstration, or grant replay/effect authority. These are two observational
contrasts, not a randomized causal intervention experiment. The earlier
both-empty results remain valid observations of a different or undetermined
state; no retrospective exact root cause is assigned.

**Stop line / follow-on design:** C1 can be closed for this *bounded*
state-association question. The next research slice should test whether an
observer can infer source and result candidates **without consulting
Google Translate's handwritten selector families**:

1. Derive a source candidate from the element receiving the consenting
   human's input event, recording only coarse, bounded semantic descriptors
   and opaque **ephemeral** within-demonstration node identity.
2. Derive a set of potential result-region candidates from *bounded
   structural changes* between the empty and translated state, without
   reading, hashing, preserving, or exporting user text.
3. Compare candidate identity/uniqueness across independently prepared
   documents and crossed output states. If zero/multiple equivalent
   candidates survive, classify `MISSING`/`AMBIGUOUS`; never silently
   adopt the handwritten reference.
4. Compare learned candidates against the handwritten reference **only after
   candidate generation**, as held-out evaluation, with provenance recorded.
   The existing reference cannot act as the source of new locator features.
5. Keep the candidate spec offline and non-executable. A separate
   user-approved, one-effect product-write budget plus source-text finality,
   translated-text stability, and lost-ACK reconciliation are later,
   independent admission gates.

No such reference-independent locator discovery or replay is yet implemented
or live-proven by the current C1 results.

### Next falsification step

Only **after live Slice B** should Slice C introduce an executable replay
candidate. That candidate needs its own explicit write authority and
post-effect ambiguity behavior, with an injected lost-ACK regression.
A structural presence trace must not be upgraded into a write or finality
permission.
