# Qwen provider: verified findings and engineering rules (2026-10-15)

Scope: draft PR #213. This is a durable engineering record, not a claim of
production readiness or of installed Windows end-to-end acceptance.

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
3. **Native extension deployment:** distinct Qwen native host and worker have
   been implemented, with offline source/packaging tests. A live Windows
   install + first browser send + continuation + restart still needs acceptance.
4. **Production promotion:** would additionally require repeated success with
   no regression to ordinary CWA/HDE, measured responsiveness, explicit choice
   handling and no uncertain-write replay. PR #213 stays Draft.

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
5. When offline and packaging gates pass, ask for **one** controlled
   authenticated end-to-end test of the isolated Qwen runtime. Capture
   `readiness → insertion → commit → POST → first text → finished` timing with
   safe metadata, but no credentials or prompt bodies in diagnostic output.
6. Check HDE/ChatGPT separately after changes to common packaging or
   installation code; keep the ordinary installed CWA unchanged.
7. Update this record with verified results, open questions and reproduction
   steps so future changes do not repeat exploratory fixes.

The source-level review and CI repair in this PR can be done via the GitHub
connector directly. A second coding agent is optional for parallel development,
not a prerequisite for ordinary diagnosis, commits, CI inspection or docs.

## Outstanding acceptance requirements

- Install and authorize the separate Qwen extension in Chrome; verify native
  registration, `qwen-native/bridge.json` and end-to-end SDK `--stream network`
  operation **without touching production CWA**.
- Check fresh new-chat, `--chat` continuation, session restart, explicit
  high-demand `/retry`, and delayed/dual-response UI.
- Measure real TTFT and finality separately. Do not infer latency from wall
  clock duration or from the interval between DOM snapshots.
- Preserve security of Qwen auth export and avoid logging request bodies,
  tokens/cookies or unrelated site traffic. Audit the native stream observer's
  payload access before wider distribution.
