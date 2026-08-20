# PR8.12 — Normalized Tool/Search Progress and User-Visible Thinking Stream

Status: IMPLEMENTED — full-stream live coverage proven; final-only option added without a separate live recheck by request.

## Goal

`cwa send --stream` should feel like the ChatGPT product while a turn is running: user-visible assistant commentary, normalized tool/search progress, bounded reasoning recap/display text, and the revision-safe final answer all arrive incrementally.

PR8.12 keeps two independent observational planes:

```text
ANSWER
assistant_text_snapshot
assistant_text_delta
assistant_text_revision
canonical_text_finalized

ACTIVITY
activity_started
activity_text_snapshot
activity_text_delta
activity_text_revision
activity_completed
```

The answer plane remains PR8.9 revision-safe and canonical HTTP readback remains final authority. Activity can never authorize a write, retry, or final response.

## Default full-stream mode

```powershell
cwa send "<prompt>" --stream
```

Representative terminal shape:

```text
I’ll verify the current stable release...
[web] Using the web…
[reasoning] Thinking…
[reasoning] Обработка заняла 13s
[snapshot]
<final assistant answer continues streaming>
```

Ordinary user-visible assistant commentary remains ordinary assistant text. It is not reclassified or hidden just because tool activity follows it.

Presentation polish guarantees line boundaries before activity, suppresses repeated generic completion noise, suppresses consecutive duplicate status lines, and removes redundant `Reasoning summary` / `Browsing update` headings when the actual recap/display text follows.

## Final-answer-only streaming

PR8.12 also supports a quieter stream:

```powershell
cwa send "<prompt>" --stream --final-only
```

The intended surface is:

```text
<no assistant commentary preamble>
<no [web] / [reasoning] / tool status>
<no reasoning recap or browsing-display text>

<only the terminal assistant answer, still streamed incrementally>
```

This is deliberately different from disabling streaming. The final assistant answer still uses PR8.9 snapshot/delta/revision delivery and canonical reconciliation.

### Final-channel evidence

Modern OpenAI assistant output can distinguish `commentary` from `final`. PR8.12 adds an optional bounded channel marker to assistant text events:

```text
channel = commentary | final | null
```

The browser layer looks only at small channel fields when present and exports no raw metadata. Explicit `commentary` is suppressed in `--final-only`; explicit `final` activates the final stream immediately.

ChatGPT web payloads may omit this marker. In that case final-only mode uses a conservative compatibility fallback:

```text
assistant message before tool/activity -> suppress
activity observed
new assistant message id              -> treat as final stream candidate
```

If neither explicit final-channel evidence nor a safe activity/new-message boundary is available, the renderer fails closed and prints the canonical final text at completion rather than leaking a possible commentary preamble.

## User-visible text policy

PR8.12 may export bounded text from explicitly user-visible activity surfaces:

```text
reasoning_recap
tether_browsing_display
```

`content_type=thoughts` remains private:

- the generic status `Thinking…` may be emitted in full-stream mode;
- raw/private thoughts text is never exported;
- thoughts never become `activity_text_*`.

Final-only mode suppresses the entire activity plane regardless.

## Tool progress normalization

Representative labels include:

```text
search_query        -> Searching the web…
open/find/click     -> Reading sources…
image_query         -> Searching images…
product_query       -> Searching products…
businesses_query    -> Searching places…
availability_query  -> Checking availability…
calculator          -> Calculating…
weather             -> Checking weather…
finance             -> Checking market data…
sports              -> Checking sports data…
time                 -> Checking time…
python/code          -> Running code…
file_search          -> Searching files…
research             -> Researching…
```

Unknown operations remain truthful generic activity such as `Using the web…` rather than inventing a specific operation.

Raw tool arguments/results are never copied into public stream events.

## First live product evidence

The production gate:

```powershell
cwa send "Search the web for the latest stable Python release, read at least two sources, and briefly tell me what changed." --stream
```

proved all central surfaces:

- user-visible assistant commentary streamed before browsing;
- normalized web activity appeared during the turn;
- reasoning status/recap appeared before the answer;
- the final assistant message remained revision-safe;
- no raw tool JSON or raw result payload appeared.

The first run also exposed presentation noise, which was subsequently polished: glued lines were separated, repeated generic completion messages were suppressed, duplicate statuses were collapsed, and redundant recap headings were removed. The user confirmed the polished output was clean.

## CLI contract

`--final-only` requires `--stream`:

```text
cwa send "..." --stream --final-only   # valid
cwa send "..." --final-only            # rejected
```

Default `--stream` behavior is unchanged.

## Safety / authority boundary

PR8.12 does not change:

- prompt insertion or submit behavior;
- model-profile selection;
- Browser Authority leases;
- PR8.11.1 early completion;
- retry policy;
- canonical finality;
- canonical readback count/reuse semantics.

The extension does not export through this layer:

- raw SSE blocks;
- raw tool arguments;
- raw tool results;
- hidden messages;
- private `thoughts` text;
- response bodies;
- headers, cookies, or credentials;
- DOM or HTML.

## Regression contract

The repository contains dedicated coverage for:

```text
full activity + answer rendering
presentation polish
bounded activity pass-through
compact {p,v} activity patches
final/commentary channel propagation
final-only explicit-channel suppression
final-only activity/new-message fallback
--final-only CLI validation
```

Per the explicit request for this small follow-up, the final-only addition was implemented without running another targeted or live gate.

## Claim boundary

PR8.12 claims:

> CWA can expose the full user-visible ChatGPT turn as a normalized live stream while keeping canonical finality authoritative and raw private/tool payloads excluded. The optional `--final-only` mode suppresses intermediate commentary and activity and streams only terminal assistant output when explicit final-channel or safe product-boundary evidence is available, otherwise failing closed to canonical final text.
