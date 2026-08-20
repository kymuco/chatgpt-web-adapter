# PR8.12 — Normalized Tool/Search Progress and User-Visible Thinking Stream

Status: LIVE PRODUCT COVERAGE PROVEN — presentation polish implemented, final regression/live recheck pending.

## Goal

`cwa send --stream` must feel like the ChatGPT product while a turn is still running, not like a final-answer-only transport.

PR8.9 already streams revision-safe visible assistant answer text. PR8.12 adds a separate activity plane for the user-visible text and progress that appears while ChatGPT reasons, searches, reads sources, runs tools, or produces a reasoning recap.

The intended terminal experience is approximately:

```text
I’ll verify the current stable release...
[web] Searching the web…
[web] Reading sources…
[reasoning] Thinking…
[reasoning] <user-visible reasoning recap / summary text when the product exposes it>

[snapshot]
<revision-safe final assistant answer stream>
```

Ordinary user-visible assistant commentary remains assistant text. PR8.12 does not demote or hide it merely because it appears before tool activity.

## Two independent planes

PR8.12 deliberately does not reinterpret tool progress as answer text.

### Answer plane

Unchanged PR8.9 contract:

```text
assistant_text_snapshot
assistant_text_delta
assistant_text_revision
canonical_text_finalized
```

Properties:

- revision-safe;
- answer sequence is independently validated;
- canonical HTTP conversation readback remains final authority;
- normalized activity events cannot affect answer reconciliation;
- user-visible assistant commentary before/during tool work remains on this plane.

### Activity plane

New normalized events:

```text
activity_started
activity_text_snapshot
activity_text_delta
activity_text_revision
activity_completed
```

Every event can carry only bounded normalized metadata such as:

```text
activity_id
activity_kind
label
tool_name
operation
source_content_type
observed_at_ms
```

`activity_text_*` additionally carries only text from explicitly user-visible activity surfaces.

## User-visible text policy

PR8.12 exports text from these bounded activity surfaces:

```text
reasoning_recap
tether_browsing_display
```

It also continues to rely on PR8.9 for ordinary visible assistant `text` / `multimodal_text` with `recipient=all`.

`content_type=thoughts` is treated differently:

- PR8.12 may emit the generic status `Thinking…`;
- raw/private thoughts content is never exported;
- `thoughts` text never becomes `activity_text_*`.

This distinction allows the CLI to reproduce the user-visible product experience without turning hidden reasoning or internal tool protocol into public stream text.

## Tool progress normalization

Tool-addressed assistant messages and tool-role results are classified browser-locally.

Representative normalized labels:

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

Unknown web/tool operations retain a truthful generic status such as `Using the web…` / `Using a tool…`; PR8.12 does not invent a more specific operation when the product schema does not prove one.

Raw tool arguments are used browser-locally only for bounded operation classification. They are never copied to an event. Raw tool results are likewise never exported by the activity layer.

## Existing command

No new CLI flag is required.

```powershell
cwa send "<prompt>" --stream
```

The same `on_event` path now carries both answer and activity planes. Existing non-streaming and JSON behavior is unchanged.

## First live product gate

The production browsing prompt was:

```powershell
cwa send "Search the web for the latest stable Python release, read at least two sources, and briefly tell me what changed." --stream
```

The observed terminal stream included all of the important surfaces:

```text
I’ll verify the current stable release from Python’s official site, then cross-check the release notes...
[web] Using the web…
[web] Web activity complete
[web] Web activity complete
[web] Using the web…
[web] Web activity complete
[reasoning] Thinking…
[web] Using the web…
[reasoning] Thinking…
[reasoning] Reasoning summary
[reasoning] Обработка заняла 13s

[snapshot]
The **latest stable Python feature-series release is Python 3.14.7** ...
```

This proves the central PR8.12 capability:

- ordinary user-visible assistant commentary streamed before tool work;
- normalized web activity appeared while browsing was active;
- reasoning status/recap surfaces appeared before the final answer;
- the final assistant answer still arrived through the revision-safe answer plane;
- no raw tool JSON or raw result payload appeared in the terminal.

The first gate therefore passed the **coverage** objective, but exposed presentation noise.

## Presentation polish after the first live gate

The first live output exposed three cosmetic issues:

```text
...matter.[web] Using the web…
[web] Web activity complete
[web] Web activity complete
[reasoning] Reasoning summary
[reasoning] Обработка заняла 13s
```

PR8.12 polish now makes the renderer:

1. guarantee a line boundary before every activity/status block, so assistant commentary can never be glued to `[web]` / `[reasoning]`;
2. suppress generic completion-only noise such as repeated `Web activity complete` while preserving specific completions such as `Web search complete` when an operation is actually proven;
3. suppress consecutive identical status lines;
4. suppress empty text-activity headings such as `Reasoning summary` / `Browsing update` when the actual user-visible recap/display text is the meaningful next surface;
5. preserve ordinary assistant commentary exactly as assistant text;
6. retain `[snapshot]` / `[revision]` semantics when a new assistant text branch begins after intermediate commentary/tool work.

Expected polished shape for the same product behavior:

```text
I’ll verify the current stable release...
[web] Using the web…
[reasoning] Thinking…
[web] Using the web…
[reasoning] Thinking…
[reasoning] Обработка заняла 13s
[snapshot]
The latest stable Python release is ...
```

Specific labels such as `Searching the web…` / `Reading sources…` remain preferred whenever operation classification proves them.

## Terminal rendering invariants

Activity statuses are rendered as labelled lines. User-visible activity text is streamed independently. The ordinary assistant answer starts on a clean line and retains PR8.9 canonical reconciliation behavior.

The renderer never uses content heuristics to decide that ordinary visible assistant text is “only commentary.” If ChatGPT says it to the user, CWA streams it.

## Safety / authority boundary

PR8.12 does not change:

- prompt insertion;
- submit behavior;
- model-profile selection;
- Browser Authority leases;
- PR8.11.1 early completion;
- retry policy;
- canonical finality;
- canonical readback count/reuse semantics.

The activity observer is best-effort. A malformed or unknown activity schema may reduce progress visibility, but cannot fail or replay a product write.

The extension does not export through this layer:

- raw SSE blocks;
- raw tool arguments;
- raw tool results;
- hidden messages;
- private `thoughts` text;
- request/response bodies;
- headers/cookies/credentials;
- DOM or HTML.

## Required regression gate after polish

```powershell
python -m pytest `
  tests/test_normalized_activity_stream_pr8_12.py `
  tests/test_revision_safe_text_delivery_pr8_9.py `
  tests/test_standalone_send_cli.py `
  tests/test_early_product_completion_repair_pr8_11_1.py `
  -q
```

The PR8.12 renderer regression now explicitly covers:

```text
assistant commentary without newline
  -> activity starts on a new line
  -> generic completion noise suppressed
  -> new final assistant message begins as [snapshot]
```

and consecutive duplicate status suppression.

## Final live recheck

After pulling the polish and reloading the unpacked extension, rerun:

```powershell
cwa send "Search the web for the latest stable Python release, read at least two sources, and briefly tell me what changed." --stream
```

Required final evidence:

```text
user-visible assistant commentary remains present
activity lines never concatenate with assistant text
generic completion spam is absent
reasoning recap text remains present
complete revision-safe final answer still streams
no raw JSON tool call is printed
no raw tool result payload is printed
canonical final answer remains correct
```

If the live product exposes an additional user-visible content type that is not covered by the current allowlist, that schema should be characterized and added explicitly rather than widening the reducer to arbitrary assistant/tool text.

## Claim boundary

Until the post-polish regression and live recheck pass, PR8.12 claims:

> Live product coverage is proven: CWA streams ordinary user-visible assistant commentary, bounded normalized web/tool activity, reasoning status/recap surfaces, and the revision-safe final answer while preserving canonical finality and excluding raw tool/private reasoning payloads. Presentation polish for line boundaries, generic-completion suppression, duplicate statuses, and redundant recap headings is implemented and awaits the final regression/live recheck.
