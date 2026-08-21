# PR8.15 — ConversationSnapshot / Export Contract & Stable Artifact Manifest

_Status: CLOSED / PASS_

_Date: 2026-08-22_

_Base: `main` after merged PR8.14 (`05e94becf54fbf00fc1cfb7716afc6192063fe09`)_

## Purpose

PR8.15 stabilizes the CWA 0.2 artifact boundary without changing product-write, browser-authority, Temporary Chat, model-selection, retry, or fallback semantics.

```text
messages  = inspect normalized canonical state now
export    = serialize normalized current branch into one portable file
snapshot  = curated context bundle plus optional forensic raw payload
manifest  = completion marker describing exact emitted files
```

`messages != export != snapshot`.

## Stable manifest schema

Every PR8.15 artifact writer emits `schema = 1` with:

```text
artifact_kind
contract
conversation_id
index
format
files[].role
files[].path
files[].media_type
files[].bytes
files[].sha256
```

The manifest contains no timestamp. Paths are manifest-relative basenames. SHA-256 is computed over exact bytes on disk. UTF-8 with LF newlines is explicit for cross-platform byte stability. The manifest is written last and is the bundle completion marker; it does not list itself.

## Snapshot contract

Existing names remain compatible:

```text
{name}_chat_context_{index}.md
{name}_chat_payload_{index}.json       # optional
```

New completion marker:

```text
{name}_chat_snapshot_{index}.manifest.json
```

Snapshot remains curated current-branch context: user messages plus user-addressed assistant messages, excluding empty/internal assistant-to-tool traffic. `--context-only` is a valid one-file bundle and does not request raw payload. Existing files are never overwritten, and manifest collisions fail closed before canonical reads.

## Export contract

`ChatGPTWebClient.export_conversation()` remains a pure string serializer. PR8.15 adds the artifact writer and CLI:

```powershell
cwa export <conversation> --format markdown|jsonl|txt
```

Aliases remain `md -> markdown` and `text -> txt`.

Written files:

```text
{name}_chat_export_{index}.md|jsonl|txt
{name}_chat_export_{index}.manifest.json
```

Export numbering is manifest-based across formats, preventing parallel index reuse when the requested format changes. Export is normalized current-branch state, not raw backend payload.

## CLI artifact envelope

`cwa snapshot ... --json` and `cwa export ... --json` expose the same outer shape:

```text
schema = 1
command
ok
conversation_id
index
message_count
manifest_path
paths
manifest
```

Absolute paths in the CLI envelope are navigation metadata. The embedded manifest is the portable contract.

## Safety

PR8.15 is read-only with respect to ChatGPT product state: canonical reads plus local filesystem writes only. It adds no product conversation write, browser tab action, automatic retry, fallback, attach/reopen authority, or Temporary lifecycle authority.

## Regression evidence

User-reported on 2026-08-22:

```text
focused PR8.15                12 passed in 0.27s
relevant artifact/CLI         47 passed in 0.48s
full repository suite       1258 passed in 22.95s
```

## Production read-only artifact smoke

Both smoke operations used the same existing durable conversation:

```text
conversation_id = 6a8733f2-d90c-83ed-a73f-08b7005a33a0
```

### Export

```text
command       = export
ok            = true
schema        = 1
index         = 1
format        = jsonl
message_count = 9
artifact_kind = conversation_export
contract      = normalized_current_branch_export_v1
file          = pr8_15_smoke_chat_export_1.jsonl
bytes         = 5563
sha256        = f9e0986015b315efc47dd707ff58b0341c039dd549ab8f41d38e29f2910d375b
manifest      = pr8_15_smoke_chat_export_1.manifest.json
```

### Context-only snapshot

```text
command       = snapshot
ok            = true
schema        = 1
index         = 1
message_count = 4
artifact_kind = conversation_snapshot
contract      = curated_current_branch_context_v1
file          = pr8_15_smoke_chat_context_1.md
bytes         = 1876
sha256        = 7892e2138500bffc0fdbe50d1db41288bb0b2d60375b16c70ec0e9df50570ca6
manifest      = pr8_15_smoke_chat_snapshot_1.manifest.json
```

The snapshot manifest contained only the context role, proving `--context-only` omitted raw payload. Export and snapshot retained distinct artifact kinds/contracts while sharing the stable schema and completion-marker model. No product write was required.

## Closure

```text
manifest schema                       PASS
exact bytes + SHA-256                 PASS
cross-format export numbering         PASS
snapshot/export contract separation   PASS
context-only raw omission             PASS
read-only production smoke            PASS
focused regression                    PASS
relevant regression                   PASS
full regression                       PASS
```

**PR8.15 — CLOSED / PASS.**
