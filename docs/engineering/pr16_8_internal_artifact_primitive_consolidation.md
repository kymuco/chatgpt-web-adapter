# PR16.8 — internal generated-artifact primitive consolidation

Issue: #193

PR16.6 and PR16.7 independently proved complete Audio and Video generated-artifact
lifecycles through authenticated browser-owned bytes and verified temporary staging.

PR16.8 consolidates only behavior that has already repeated in both artifact types.
It does not add a new product capability.

## Slice 16.8a — one internal browser byte-retrieval core

The Audio and Video browser byte probes previously duplicated the same sequence:

```text
exact artifact-local menu
→ structural save_alt
→ browser sink guard
→ Download effect boundary
→ product-created window.open locator
→ Googleusercontent locator policy
→ authenticated Network.loadNetworkResource
→ media-family admission
→ IO.read
→ SHA-256
→ Native Messaging chunks
```

They now delegate to one internal helper:

```text
_cwaGeminiNotebookProbeArtifactBytes(message, port, profile)
```

Audio and Video remain separate operation contracts. Their wrappers provide only the
evidence-backed differences:

```text
Audio:
  mediaFamily = audio
  Audio chunk type / error namespace
  historical requireCompletedExactRef = false
  historical mediaFamily result field omitted

Video:
  mediaFamily = video
  Video chunk type / error namespace
  requireCompletedExactRef = true
  mediaFamily result field retained
```

The consolidation deliberately preserves these historical observable contracts rather
than "improving" them during refactoring.

The shared core owns the already-proven safety invariants:

```text
effect boundary before Download click
automaticRetry = false after the boundary
raw signed locator never exported
private Google protocol body never read
no final destination publication
authenticated browser-owned network load
bounded byte count + SHA-256
```

This remains an internal Notebook implementation detail. No public
`HostedArtifactLifecycle`, registry/factory, universal artifact schema, or caller
filesystem publication authority is introduced.


## Slice 16.8b — one internal Python temporary-staging core

Audio and Video Python byte probes also duplicated the same staging implementation:

```text
ordered chunk admission
→ manifest consistency
→ base64 decode
→ max-byte enforcement
→ sequential staging write
→ incremental SHA-256
→ fsync
→ full staging re-read
→ size/hash verification
```

That implementation now lives in the private module:

```text
_gemini_notebook_artifact_staging.py
```

with one internal collector and one max-byte normalizer.

The existing private compatibility names remain in their artifact-specific modules:

```text
_AudioArtifactByteChunkCollector
_VideoArtifactByteChunkCollector
_normalize_max_bytes
```

Each collector supplies only its historical error namespace
(`AUDIO_ARTIFACT` or `VIDEO_ARTIFACT`) to the shared core, preserving the existing
diagnostic strings and tests.

RPC orchestration, operation names, result contracts, temporary-file lifecycle, and
public/module-only surfaces remain separate in this slice. No public staging API is
introduced.
