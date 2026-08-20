# PR8.12 — Normalized Tool/Search Progress and User-Visible Thinking Stream

Status: IMPLEMENTED — live product gate pending.

## Goal

`cwa send --stream` must feel like the ChatGPT product while a turn is still running, not like a final-answer-only transport.

PR8.9 already streams revision-safe visible assistant answer text. PR8.12 adds a separate activity plane for the user-visible text and progress that appears while ChatGPT reasons, searches, reads sources, runs tools, or produces a reasoning recap.

The intended terminal experience is approximately:

```text
[reasoning] Thinking…
[web] Searching the web…
[web] Reading sources…
[reasoning] <user-visible reasoning recap / summary text when the product exposes it>

<revision-safe assistant answer stream>
```

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
- normalized activity events cannot affect answer reconciliation.

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

Unknown tools are represented only as a generic `Using a tool…` activity.

Raw tool arguments are used browser-locally only for bounded operation classification. They are never copied to an event. Raw tool results are likewise never exported by the activity layer.

## Existing command

No new CLI flag is required.

```powershell
cwa send "<prompt>" --stream
```

The same `on_event` path now carries both answer and activity planes. Existing non-streaming and JSON behavior is unchanged.

## Terminal rendering

Activity statuses are rendered as labelled lines, for example:

```text
[web] Searching the web…
[web] Web search complete
```

User-visible activity text is streamed independently:

```text
[reasoning] Reasoning summary
[reasoning] <snapshot><delta><delta>...
```

Then the ordinary assistant answer starts on a clean line and retains the PR8.9 canonical reconciliation behavior.

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

## Required regression gate

```powershell
python -m pytest `
  tests/test_normalized_activity_stream_pr8_12.py `
  tests/test_revision_safe_text_delivery_pr8_9.py `
  tests/test_standalone_send_cli.py `
  tests/test_early_product_completion_repair_pr8_11_1.py `
  -q
```

## Required live gate

After pulling and reloading the unpacked extension, use a turn that explicitly requires browsing:

```powershell
cwa send "Search the web for the latest stable Python release, read at least two sources, and briefly tell me what changed." --stream
```

Expected minimum evidence:

```text
at least one normalized activity line before/during the answer
complete revision-safe final answer still streams
no raw JSON tool call is printed
no raw tool result payload is printed
canonical final answer remains correct
```

Preferred evidence on the current product schema is one or more of:

```text
[web] Searching the web…
[web] Reading sources…
[reasoning] Thinking…
[reasoning] <visible recap text>
```

If the live product exposes an additional user-visible content type that is not covered by the current allowlist, that schema should be characterized and added explicitly rather than widening the reducer to arbitrary assistant/tool text.

## Claim boundary

Until the live gate passes, PR8.12 claims:

> CWA has a separate normalized activity stream that can carry bounded user-visible reasoning recap/browsing-display text and tool/search progress while preserving PR8.9 answer reconciliation and canonical finality. Production coverage of the current live ChatGPT activity schemas remains pending the explicit live browsing gate.
