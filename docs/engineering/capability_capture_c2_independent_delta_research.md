# Capability Capture C2 — independent event/delta discovery (research)

**Status:** research-only; one live proof not yet performed. This is a
**stacked draft** based on C1 PR #201. Production main is unchanged.

## Research question

Can a browser observer recover a plausible source-control identity and a
bounded result *change candidate* from a single human demonstration **without
using the handwritten Translate selector families to generate candidates**?

C1 proved that one existing handwritten source/result family had matching
structural signatures on two page documents and that the result-family
footprint flipped under manual crossed output states. That does not support a
learned locator. C2 must not inherit candidate selectors from that result.

## C2a: one-tab, explicit-consent capture

\`research_capture_independent_delta_v0\` is routed under the existing
Google Translate domain into the same exclusive native-host authority lane.
It observes a single caller-selected tab. Exact Google Translate origin and
\`sl/tl\` are a **security boundary**, not locator-generation features.

The page probe installs a temporary, capturing-phase trusted \`input\` event
listener and a scoped \`MutationObserver\` on the page document. The browser
operation is read-only with respect to product state, although observation
temporarily installs event listeners and an in-page closure which are removed
in a mandatory cleanup path. It never invokes a text setter, button click,
navigation, page activation, script injection with user content, or retry.

- **Source discovery:** only the actual, trusted human input event target.
  The target must be an eligible, visible generic \`input\`, \`textarea\`, or
  \`contenteditable\`; no Translate selector. Ephemeral DOM identity stays
  in page memory. Different eligible input targets → \`AMBIGUOUS\`, not
  "leftmost".
- **Candidate result discovery:** only changed/added generic DOM leaf
  elements observed *after* that source event. Child-list,
  character-data, and visibility-related attribute mutations can contribute.
  Exclude source ancestors/descendants, controls and disconnected/hidden
  nodes. No output text is inspected, compared or hashed.
- **Bounds:** 6–20 second observation; up to 64 trusted input events,
  8 distinct changed leaves, traversal budget 24 nodes per mutation.
  Overflow explicitly fails closed. At least 1s of structural quiet is
  required before classifying **one** candidate.
- **Export:** closed-enum source/leaf role, element kind, and coarse
  left/center/right viewport region, plus small counts and flags. No page
  text, attributes, ids, XPaths, CSS selectors, node fingerprints/hashes,
  raw DOM, screenshots, network bodies, cookies, tab URLs or tab IDs in the
  final report. A synthetic test rejects any such additional response data.
- **Cleanup:** removal of observer/listener plus debugger detach must be
  proven even on failure. A missing ACK is an error with no retry.

This deliberately tests a weaker property than semantic result identity.
The observed candidate could be a spinner, tooltip, highlight, keyboard
helper or another bystander DOM mutation. A single generic structural leaf
must **not** be called a learned translation locator. There is no forced
fallback to existing Translate selectors.

## Safe local experiment

After the exact-head CI passes, install/reload the **research** extension
from this stacked branch. Select a single Google Translate tab with route
\`https://translate.google.com/?sl=en&tl=es&op=translate\`. Manually clear
the source and verify that the prior translated text is gone **before**
starting the command (the observer neither reads source content nor clears
it). Obtain the current tab ID via research service worker DevTools:

\`\`\`javascript
chrome.tabs.query({ url: "https://translate.google.com/*" }).then(tabs =>
  console.table(tabs.map(tab => ({ id: tab.id, active: tab.active })))
);
\`\`\`

Start this in PowerShell with the actual tab ID:

\`\`\`powershell
python -m tools.capability_capture_c2_browser `
  --tab-id <EXACT_TRANSLATE_TAB_ID> `
  --source-language en `
  --target-language es `
  --seconds 16 `
  --i-consent-to-independent-capture
\`\`\`

Immediately after the command starts, **the human** types a harmless
\`hello\` into the existing source field, leaving the page otherwise alone.
Do not use another automation to enter this text. The script itself never
writes it. It may return \`MISSING\`, \`AMBIGUOUS\`, a single generic
changed-leaf candidate, or a failure/overflow. All are informative research
outcomes. In all cases, replay and write authorization remain prohibited.

## First real C2 attempt — no accepted input event (2026-10-08)

The first human-operated live run on exact `20ce654d7a0d920d5ab41c479866e06a3edc4de1`
completed without transport/cleanup failure, but returned:

```text
capture_classification    INCOMPLETE_OR_AMBIGUOUS_STRUCTURAL_DEMONSTRATION
input_event_count         0
source.status             MISSING
result.status             MISSING
structural_quiet          false
replay_executable         false
new_write_authority       false
```

This **does not mean** the browser emitted no `input` events. The original
counter incremented only after the `isTrusted`, eligible element-kind and
visibility filters. Nor does the output confirm whether the operator typed
while the observer was installed. Therefore it is not a result-selector
failure and does not justify changing candidate discovery.

### C2 input-filter diagnosis

The research protocol is now explicitly versioned as
`CWA_CAPTURE_C2_INDEPENDENT_DELTA_V1` to require a closed, bounded
`inputFilterCounts` object in addition to the accepted event count:

```text
observed            all dispatched input events seen by capture listener
trusted             observed events with event.isTrusted === true
unsupportedTarget   trusted input targets outside eligible generic controls
invisibleTarget     trusted eligible input targets failing visibility test
eligible            trusted / eligible / visible input events (old count)
```

Every count is an integer from 0 through 64, and must satisfy
`observed >= trusted` and
`trusted = unsupportedTarget + invisibleTarget + eligible`.
Greater than 64 observed events sets overflow and fails closed.
`observerWindowMs` measures the bounded time **after successful listener
installation**, rather than the earlier browser attachment period; it is
between 0 and 20,000 ms. No key, typed text, event.data, text hash, element
name, selector, URL, node ID or DOM snapshot is captured or returned.

The final Python report adds `input_filter_counts`,
`input_detection_diagnosis`, and `observer_window_ms` to distinguish
no observed events, only untrusted events, filtered targets or accepted
events. A count of zero **cannot** by itself prove why the human's typing
did not appear. Old V0 responses must fail strict V1 admission.

The next explicit-consent live capture should begin from a cleared Translate
source, enter harmless `hello` **after the observation has started**, and
leave the tab otherwise undisturbed. Its result is a diagnostic observation,
not proof of learned source/result locator, translation identity or replay
authority. No blind retry or automatic product write is allowed.

## Admission and falsification

Strict outer RPC timeout reserves ten seconds for native-host response
relative to the delegated budget, and never retries after delegation.

C2 returns a non-executable report:

\`\`\`text
source.provenance            TRUSTED_HUMAN_INPUT_EVENT
result.provenance            POST_INPUT_GENERIC_DOM_MUTATIONS
reference_selector_consulted false
source_selector_learned      false
result_selector_learned      false
result_semantic_identity     false
semantic_finality_proven     false
replay_executable           false
new_write_authority         false
automatic_retry             false
raw_content_retained        false
\`\`\`

Initial offline gates include a synthetic event target, inserted/changed
generic DOM leaves, ambiguous multiple sources/results, untrusted event
rejection, privacy/authority spoofing, cleanup loss and preservation of the
existing Translate domain's routing.

**No held-out comparison against the reference selector family has yet
been made.** That evaluation must happen **after** candidate generation
and only when the two independent observations are matched by explicitly
verified page state. Never allow reference selectors to influence candidate
generation. Distinct live examples and UI variations are still needed.
Proof of semantic completion, translation correctness, and lost-ACK
reconciliation are separate later gates before any executable replay.
