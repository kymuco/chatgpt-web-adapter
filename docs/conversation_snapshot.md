# Deterministic conversation snapshots

The snapshot CLI turns one existing ChatGPT conversation into a compact research-context file plus an optional raw-payload backup.

## Quick use

After installing the package, both command names point to the same CLI. The short form is intended for frequent use:

```powershell
cwa snapshot "https://chatgpt.com/c/<conversation-id>" --name organism_lab
```

Equivalent long form:

```powershell
chatgpt-web-adapter snapshot "https://chatgpt.com/c/<conversation-id>" --name organism_lab
```

With no explicit `--index`, the command scans the output directory for existing matching context snapshots and selects `max(existing_index) + 1`.

For example, if `organism_lab_chat_context_11.md` exists, the next command writes:

```text
organism_lab_chat_context_12.md
organism_lab_chat_payload_12.json
```

The default output directory is the current directory. Use `--output-dir <path>` to change it.

## Clean context contract

The Markdown context is intentionally narrow and deterministic:

- current conversation branch only;
- roles limited to `user` and `assistant`;
- empty/whitespace-only messages removed;
- assistant messages with an internal recipient are removed;
- assistant messages are kept only when `recipient` is absent or equals `all`;
- retained text is stripped at both ends;
- blocks are rendered as `## USER` / `## ASSISTANT` and separated by `---`.

This matches the intended handoff context rather than a forensic transcript of internal tool traffic.

## Raw backup

By default the command also writes the complete conversation payload returned by the existing authenticated web-session read path:

```text
<name>_chat_payload_<index>.json
```

The raw file is UTF-8 JSON with Unicode preserved. It is a local forensic backup and can contain substantially more conversation metadata than the clean Markdown context, so handle it as sensitive project data.

To skip the raw backup:

```powershell
cwa snapshot "https://chatgpt.com/c/<conversation-id>" --name organism_lab --context-only
```

## Explicit numbering

Use `--index N` when a caller such as CMA owns the generation number:

```powershell
cwa snapshot "https://chatgpt.com/c/<conversation-id>" --name organism_lab --index 12
```

Existing target files are never overwritten. An explicit collision fails before the conversation is read.

## Dependencies

The feature adds no runtime dependency. It uses the package's existing `ChatGPTWebClient`, `ConversationRef`, `pathlib`, and Python standard-library JSON support.
