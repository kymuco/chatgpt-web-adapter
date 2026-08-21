# Standalone `cwa send`

`cwa send` is the human-oriented terminal entrypoint for one ordinary ChatGPT product turn. It is a thin usability layer over the existing `ChatGPTProductRuntime`; it does not introduce a second write path.

## Default behavior

```powershell
cwa send "Explain this result"
```

The standalone CLI deliberately defaults to semantic profile `DEEP`, which maps through the proven PR8.10 selector to product mode `HIGH`.

This is a CLI usability policy only. The Python `ChatGPTProductRuntime` keeps its existing `model_profile=None` default so library callers retain explicit control and compatibility.

Plain invocation prints only the final canonical assistant text.

## Continue a conversation

```powershell
cwa send "Continue from the previous result" --conversation <conversation-id>
```

The standalone send surface currently accepts the same conversation value as `ChatGPTProductRuntime`: use a conversation id for continuation.

## Model profiles

Supported standalone profiles are:

```text
FAST      -> INSTANT
BALANCED  -> MEDIUM
DEEP      -> HIGH (default)
```

Examples:

```powershell
cwa send "Give me a quick answer" --profile FAST
cwa send "Analyze the tradeoffs" --profile BALANCED
cwa send "Do a deep technical review" --profile DEEP
```

Profile names are case-insensitive. `MAX` remains intentionally unavailable because the proven product selector has only the three mapped slider states.

Explicit profile selection is fail-closed in the production runtime. The CLI does not silently fall back to another product mode.

## Revision-safe streaming

```powershell
cwa send "Explain the architecture" --stream
```

Streaming uses the proven PR8.9 `on_event` revision-safe surface, not the legacy `on_token` compatibility callback.

Append-only extensions appear naturally. If already displayed provisional text is revised, the portable terminal renderer starts a labelled revision/canonical block rather than pretending the source was an append-only token stream. Canonical final text remains authoritative.

The renderer also reuses PR8.9 sequence validation, so duplicate or reordered text observations are not blindly printed twice.

## Machine-readable output

```powershell
cwa send "Inspect this" --json
```

`--json` returns the same structured observed execution shape used by the lower-level `runtime send` command, including conversation identity, runtime observation and provenance.

`--stream` and `--json` are mutually exclusive so stdout has one clear contract.

## Compatibility boundary

The existing command remains available:

```powershell
cwa runtime send "..."
```

It remains the lower-level machine-oriented runtime command and keeps its existing behavior. In particular, this standalone feature does not impose the `DEEP` default on `ChatGPTProductRuntime` itself or on `runtime send`.
