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
