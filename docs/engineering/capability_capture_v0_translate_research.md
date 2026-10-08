# Capability Capture v0 — Google Translate falsification, slice A

Status: **RESEARCH-ONLY / NON-EXECUTABLE**. Baseline:
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
   in the route; ensure the source field is **empty**.
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

### Evidence boundary and explicit incompleteness

A clean offline CI proves static input validation, response admission and
synthetic DOM evidence only. It cannot prove that the current live Google
Translate UI exposes compatible selectors or that attaching CDP while the
user types is reliable on all browser versions.

Slice B is not closed until a human performs at least one consented, observed
real-product demonstration and reports whether the instrument attached,
captured events, preserved privacy and detached cleanly. A failed capture is
an experimental result; do not silently switch to a different browser
transport, infer finality or automatically repeat the user action.

### Next falsification step

Only **after live Slice B** should Slice C introduce an executable replay
candidate. That candidate needs its own explicit write authority and
post-effect ambiguity behavior, with an injected lost-ACK regression.
A structural presence trace must not be upgraded into a write or finality
permission.
