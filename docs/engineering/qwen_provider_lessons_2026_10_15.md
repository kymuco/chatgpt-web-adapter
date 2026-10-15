# Qwen provider: verified findings and engineering rules (2026-10-15)

Scope: draft PR #213. This is a durable engineering record. The user and
Codex performed successful **installed Windows Python SDK end-to-end tests
before pushing commit `bec72b31`**. This proves a working baseline, not
uninterrupted reliability or production readiness.

## Evidence levels (do not confuse these)

1. **Static/unit tests:** deterministic Python and Node mocks prove the stated
   invariants only. A green CI matrix is not a successful live Qwen turn.
2. **Direct browser-CDP experiment:** Codex's documented run in
   [qwen_background_observation_2026_10_15.md](qwen_background_observation_2026_10_15.md)
   showed an authenticated hidden-tab Send with Qwen create/completion
   HTTP 200 and a finished text/event-stream response. It exercised provider
   helper functions using a diagnostic CDP event adapter, **not** the installed
   Python SDK/native messaging path. The trace is described in the repo but is
   not a separately replayable full E2E CI fixture.
3. **Installed Windows SDK end-to-end (USER CONFIRMED):** before the Codex
   commit was pushed, the user ran
   `python qwen_sdk.py --auto-confirm-age --birth-year 2000 --stream network`.
   In one interactive session, Qwen answered `привет`, enumerated **1–100**
   completely, and replied to `круто молодец`. A later query about Formula 1
   returned `QWEN_POST_SUBMIT_UI_UNOBSERVED_AFTER_WRITE_OR_NAVIGATION` with
   `write=completion network=finished http=200`. In a **new SDK process**,
   `python qwen_sdk.py --chat REDACTED_QWEN_CHAT_UUID
   --auto-confirm-age --birth-year 2000 --stream network` correctly recovered
   the previous messages, **including** the Formula 1 question. This proves
   successful new-chat, continuation, network answer delivery and explicit
   conversation reattachment across processes. It also proves that the
   ambiguous UI error can occur **after a durable user message**.
   A separate initial run reported `write=none network=unobserved`,
   `editor=empty send=missing visibility=visible`. **User/Codex diagnosis:**
   the encountered failures corresponded to Qwen's busy/high-demand state,
   rather than an independent known transport defect. These coarse diagnostic
   fields do not independently prove that attribution: `write=none` means
   only no matching POST was observed. The documented recovery is the
   explicit `/retry` command, not submitting the same prompt again.
4. **Recovery implemented:** `/retry` already exists. It dispatches a
   dedicated `regenerate` operation, checks the last response for the
   Qwen high-demand message, and clicks its enabled **Regenerate** control
   once in the *same* chat; it does not replay the user prompt. This addresses
   the overload scenario diagnosed by the user and Codex. No automatic retry.
5. **Production promotion:** operational reliability under changing Qwen
   behavior, dual-response selection, measured responsiveness and no
   regression to ordinary CWA/HDE remain separate concerns. PR #213 stays
   Draft; do not invent a distinct Send/DOM bug merely from these busy traces.

## What our earlier debugging got wrong

- We treated `textarea.value === prompt` as equivalent to application state
  and successful Send. It is not. React/composer focus and the browser input
  pipeline must be validated separately from DOM value and button presence.
- We changed DOM click, CDP mouse events, timeouts and active/hidden-tab mode
  in response to each failure. That obscured the root cause. In particular,
  reproducing `write=none editor=prompt_present send=enabled visibility=visible`
  disproved the claim that **background visibility alone** caused failure.
- Before relying on CDP `Input.insertText` in an inactive tab, the diagnostic
  environment had to explicitly manage focus. The independent worker now
  issues `Emulation.setFocusEmulationEnabled({enabled:true})` before
  `Input.insertText`; Qwen keeps a single Send commit action. This is a
  targeted, testable control-surface behavior, **not** a universal rule for
  React apps or evidence that all CWA failures had this cause.
- We relied on a 9s then 3.5s DOM quiet period as if it proved completeness.
  In the Codex diagnostic a completed, verified SSE answer enumerated to 60
  while hidden-page DOM contained only 15. DOM stable and Stop absent are
  **not** server-authoritative completion signals.
- Our initial Qwen implementation imported provider modules into production
  CWA's service worker. During that deployment, HDE reported
  `CHATGPT_SUBMIT_NOT_OBSERVED:send_button_click`. HDE recovered after
  restoring two shared extension files. This is a correlated rollback, **not
  a proof of which file or JavaScript behavior was responsible**.
- We concluded a second Chrome profile was mandatory. It is not, by itself,
  sufficient for isolation: independent native-messaging identity and
  independent bridge descriptor/state root are essential.

## Patterns to reuse

### Separate authority and transport boundaries

- Production ChatGPT/HDE retains `com.kymuco.chatgpt_web_adapter`,
  its original extension imports/manifest and its own `browser-native/bridge.json`.
- Experimental Qwen uses `com.kymuco.qwen_web_adapter`, its own unpacked
  extension/worker and `qwen-native/bridge.json`. Installer registration must
  be explicit and must not overwrite production registration, state or profile.
- One shared Python package can expose both SDK entry points, but **package
  sharing does not imply a shared browser runtime or native bridge**.
- Test both isolation in source and actual packaged wheel/sdist artifacts.
  `tools/release_gate.py` is a required contract. The original Codex commit
  `bec72b31` passed OS/Python tests but failed this release gate because
  it added the Qwen native console script without updating the expected
  console-entry-point set. Follow-up release tests fixed this oversight.

### Submission is a state machine, not one click

```text
tab/site ready
  → age/feedback gates resolved
  → exact empty composer verified
  → focus established
  → one browser-generated text insertion
  → application send readiness inspected
  → exactly one commit attempt
  → outgoing request evidence (when observable)
  → response stream/finality evidence
  → conversation identity bound to route
```

- A text-in-field check is not proof of React acceptance. Network-observed
  POST is evidence of a request, not yet of accepted and completed generation.
- After any possibly executed Send, lost responses, a detached debugger or
  a timeout create an **ambiguous write**: reconcile manually; never auto-send
  the user prompt again. Treat `write=none` as *observer saw no matched POST*,
  not categorical proof that nothing went out.
- For Qwen high-demand errors, `/retry` is an **explicit human-commanded**
  *Regenerate* click in the same chat, not an automatic replay and not a new
  user-message submission. Require positive UI evidence of the high-demand
  error; missing or changed control fails closed.
- `--chat` attaches only to a validated exact-origin Qwen conversation URL/
  UUID and must not silently create a replacement chat when a route is unknown.

### Distinguish response evidence and display

- Qwen's `Network.streamResourceContent` plus bounded SSE parser reconstructs
  only `phase=answer` deltas. Respect split UTF-8 frames, late buffered events
  and explicit answer-finished evidence. Verify before returning collected text.
- In `--stream network`, return the verified assembled SSE text, **not** the
  possibly truncated final DOM snapshot. Keep canonical/durable completion
  unproven unless a separately validated canonical source exists.
- The CLI currently defaults to `--stream dom`, which remains heuristic.
  **Use `--stream network` for completeness testing.** Do not claim that
  the default DOM mode has the same completeness guarantee.
- Dual `Response 1` / `Response 2` feedback is a required user selection,
  not a race to pick the first or last candidate. The other reply may be
  preserved only with explicit identity and without corrupting the chosen
  conversation branch.

## A faster and safer development loop

1. Record one reproducible **observed fact** and one hypothesis; do not call
   a hypothesis a fix. Separate pre-click, post-click, network, response-DOM
   and native-bridge outcomes.
2. Read the live code and compare the exact PR diff with production. Check
   host/descriptor/import-graph isolation **before** asking for any deployment.
3. Implement the smallest safe change with deterministic regressions for both
   successful and ambiguous outcomes. Do not add automatic replay.
4. Verify engineering quality, Python/OS matrix, **build release artifacts**,
   installed wheel and native-host script/worker packaging. A green unit suite
   alone is insufficient. Inspect workflow job logs and repair actual failures.
5. **Do not repeat acceptance tests already demonstrated by user transcripts.**
   Preserve the user-confirmed successful new-chat, continuation, SSE delivery
   and `--chat` reattachment as the baseline. For *new regressions* capture
   `readiness → insertion → commit → POST → first text → finished` timing with
   safe metadata and no credentials or prompt bodies. Prioritize specifically
   evidence of overload versus any genuinely new failure. Do not reopen
   the already diagnosed busy incidents as unrelated Send/DOM defects.
6. Check HDE/ChatGPT separately after changes to common packaging or
   installation code; keep the ordinary installed CWA unchanged.
7. Update this record with verified results, open questions and reproduction
   steps so future changes do not repeat exploratory fixes.

The source-level review and CI repair in this PR can be done via the GitHub
connector directly. A second coding agent is optional for parallel development,
not a prerequisite for ordinary diagnosis, commits, CI inspection or docs.

## Outstanding acceptance requirements

- **Already verified on user's Windows machine:** installed Qwen SDK browser
  transport, new-chat, multi-turn continuation, network SSE text and explicit
  `--chat` reattachment in a new process. Do not reclassify these as untested.
- **Already implemented to address the user-observed busy incidents:**
  explicit `/retry` -> one gated Regenerate in the same chat. This is
  separate from prohibited automatic retry/replaying a submitted prompt.
- **Potential future coverage:** changing high-demand UI selectors,
  delayed/dual-response selection, long-running sessions and measured latency.
  Do not classify the supplied `write=none` / HTTP-200-without-DOM traces
  as unsolved transport bugs without new evidence beyond the known busy state.
- Measure real TTFT and finality separately. Do not infer latency from wall
  clock duration or from the interval between DOM snapshots.
- Preserve security of Qwen auth export and avoid logging request bodies,
  tokens/cookies or unrelated site traffic. Audit the native stream observer's
  payload access before wider distribution.
