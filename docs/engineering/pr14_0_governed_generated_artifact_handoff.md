# PR14.0 — Governed Generated Artifact Handoff

## Purpose

PR13.1–PR13.4 established the read-side chain for a ChatGPT-generated artifact:

```text
saved conversation
  -> explicit product-owned file_id
  -> identity-bound resolver
  -> approved locator
  -> exact artifact bytes
  -> byte-count / SHA-256 integrity evidence
  -> longitudinal identity stability
```

Those experiments deliberately stopped before filesystem authority. PR14.0 promotes
that evidence into one bounded production capability: materialize one caller-named
generated artifact to one caller-authorized local destination without turning an
observed product locator into filesystem or retry authority.

## Candidate public operation

The production operation is intentionally narrow:

```python
result = client.handoff_generated_artifact(
    conversation,
    filename="report.pdf",
    destination="./exports/report.pdf",
    overwrite=False,
)
```

The current implementation core is
`chatgpt_web_adapter.generated_artifact_handoff.handoff_generated_artifact`; the
client/runtime binding and root-package classification are completed in this PR
before merge.

The success value is `GeneratedArtifactHandoffResult` and contains only stable,
non-locator evidence:

```text
conversation_id
source_filename
destination
size_bytes
sha256
overwritten
integrity_verified = true
```

It does **not** expose the product `file_id`, resolver payload, locator, signed query,
credentials, or artifact bytes.

## Authority model

### Product identity

The human-readable filename is a selector, not identity.

PR14.0 accepts only an explicit `file_id` from the conversation-scoped files
collection as production artifact identity. Research fallback candidates such as
`artifact_id`, `asset_id`, or generic `id` are not silently promoted.

```text
filename selector != product identity
file_id = product identity
```

Zero filename matches fail closed. Multiple filename matches fail closed. A unique
filename match without a valid `file_id` fails closed.

### Destination authority

The caller must provide the exact destination path. PR14.0 does not infer a download
folder, reuse the source filename as local authority, create parent directories, or
pick a replacement path.

Before any network read:

- the destination parent must already exist and be a directory;
- a symlink destination is rejected;
- an existing non-regular destination is rejected;
- an existing regular file is rejected unless `overwrite=True` was supplied.

The default is therefore:

```text
existing destination -> fail before download
```

### Overwrite authority

`overwrite=False` is protected both before retrieval and at publish time. The final
no-overwrite publication uses an atomic same-directory hard-link from the staged
artifact, so a file that appears after the initial authority check causes a
fail-closed `DESTINATION_EXISTS` rather than a hidden overwrite.

`overwrite=True` authorizes replacement of a regular destination at that exact
path. It does not authorize directory replacement or symlink traversal.

## Read chain

A successful handoff uses the already-characterized PR13 chain:

1. one authenticated read of
   `/backend-api/conversations/{conversation_id}/files`;
2. one authenticated read of
   `/backend-api/files/download/{file_id}?conversation_id=...&inline=false`;
3. one non-redirecting GET of the approved resolver locator.

There is no endpoint fallback and no automatic request retry in this capability.

## Locator and credential policy

The PR13.3 locator policy becomes a production invariant.

Allowed locator classes:

- `https://chatgpt.com/...`;
- `https://oaiusercontent.com/...`;
- `https://*.oaiusercontent.com/...`.

Rejected:

- non-HTTPS URLs;
- URL userinfo;
- fragments;
- non-default ports;
- any other origin;
- redirects.

Credential forwarding is origin-bound:

```text
chatgpt.com locator
    -> authenticated ChatGPT headers allowed

oaiusercontent.com locator
    -> no ChatGPT Authorization header
    -> no ChatGPT Cookie header
```

The dedicated handoff read path does not route resolver or artifact response bodies
through the normal debug HTTP body trace writer. This prevents an enabled debug
trace from silently persisting signed locators or generated artifact bytes.

## Bounded retrieval

The default artifact size ceiling is 1 GiB:

```text
DEFAULT_GENERATED_ARTIFACT_MAX_BYTES = 1073741824
```

The caller may supply a different positive `max_bytes` value explicitly. Retrieval
is written directly into a sibling staging file rather than accumulated in Python
memory.

## Materialization transaction

The artifact is never downloaded directly into the caller-visible destination.

```text
approved locator
    -> unique sibling .part staging file
    -> retrieval complete
    -> fsync staging file
    -> compute staged byte count + SHA-256
    -> compare product size metadata when present
    -> atomic publish
    -> re-read destination
    -> verify exact byte count + SHA-256
    -> success result
```

For `overwrite=False`, publication is atomic no-replace. For `overwrite=True`,
publication uses `os.replace`.

Staging files are cleaned on all pre-publish failures.

## Ambiguous filesystem failure

A publish attempt is a write boundary. If the operating system reports a publish
failure for which final destination state cannot be proven, PR14.0 reports:

```text
destination_state = unknown_after_publish_attempt
```

and stops. It does not retry the write automatically.

If post-publication integrity verification fails, PR14.0 reports:

```text
destination_state = published_unverified
```

and likewise does not retry, delete, or overwrite again automatically.

This preserves the same broader CWA rule used for product writes:

```text
ambiguous write != retry authority
```

## Stable failure surface

`GeneratedArtifactHandoffError` reports bounded fields only:

```text
reason
stage
status_code
destination_state
```

The failure surface never includes `file_id`, resolver locator, signed query,
credentials, resolver body, or artifact bytes.

Stages are:

```text
authority
discovery
resolution
retrieval
publish
verification
```

## Scope boundaries

PR14.0 does not add:

- bulk artifact download;
- destination inference;
- implicit parent-directory creation;
- arbitrary URL download;
- redirect following;
- resumable download;
- automatic network retry;
- automatic filesystem retry;
- automatic rollback after an ambiguous publish;
- product-side writes or mutations.

The capability is a governed handoff from already-proven product-owned identity to
one explicit local filesystem destination.

## Acceptance target

Before merge, PR14.0 requires both deterministic regression coverage and one
authenticated exact-head live gate against the existing PR13 generated text fixture:

```text
filename = cwa_pr13_1_identity_probe.txt
size = 45
sha256 = d0bb354d72fad3715f5348740d75dd644435165f68034f54f7974c834cbe9f1d
```

The live gate must prove on the exact candidate SHA:

```text
identity-bound discovery = PASS
resolver = PASS
locator policy = PASS
local materialization = PASS
materialized size = 45
materialized SHA-256 = expected
post-write integrity = PASS
implicit overwrite = REJECTED
automatic retry = NOT ATTEMPTED
```

The fixture destination is local only; the live gate performs no ChatGPT/product
write.
