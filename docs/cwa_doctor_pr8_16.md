# PR8.16 — `cwa doctor`: Environment, Bridge, Runtime & Artifact Diagnostics

_Status: CLOSED / PASS_

_Date: 2026-08-22_

_Base: `main` after merged PR8.15 (`aaefd9abca1e284041a187f76f358f4c6a5d0b2b`)_

## Purpose

PR8.16 adds one safe preflight surface for CWA 0.2:

```powershell
cwa doctor
cwa doctor --json
```

The command is intentionally read-only. It observes existing state, classifies failures, and prints remediation guidance. It does **not** perform repair actions.

It adds no ChatGPT product write, auth refresh, interactive login, Native Messaging install, browser extension reload, browser tab action, automatic retry, fallback transport, artifact rewrite, or Temporary lifecycle authority.

## Diagnostic model

`doctor` reuses existing CWA sources of truth:

```text
environment  -> Python/package/platform + frozen extension-id integrity
auth         -> get_auth_status()
install      -> packaged extension + Native Messaging manifest/registration
bridge       -> BrowserNativeTurnProvider.status()
runtime      -> ChatGPTProductRuntime.health() + capabilities()
artifact     -> PR8.15 manifest/files/hash verification when requested
```

Stable check states:

```text
PASS  check is satisfied
WARN  non-blocking condition worth attention
FAIL  required condition is not satisfied
SKIP  optional check was not requested/applicable
```

`WARN` and `SKIP` do not fail the report. Any required `FAIL` makes `ok=false`.

PR8.16 reuses the PR8.14 exit-code contract:

```text
0  doctor completed and no required check failed
1  doctor completed but one or more required checks failed
2  usage/input validation failure
3  operational failure outside the classified doctor report
4  existing reconciliation-required ambiguous-write class
```

Because `doctor` performs no write, it does not create a new exit-4 condition.

## Stable JSON schema

`cwa doctor --json` returns schema `1`:

```json
{
  "schema": 1,
  "command": "doctor",
  "ok": true,
  "summary": {
    "pass": 0,
    "warn": 0,
    "fail": 0,
    "skip": 0
  },
  "checks": [
    {
      "id": "runtime.health",
      "section": "runtime",
      "status": "PASS",
      "summary": "Product runtime is ready",
      "required": true,
      "evidence": {},
      "remediation": null
    }
  ]
}
```

Evidence contains diagnostic metadata only. Auth checks never export access-token values, session-cookie values, bridge tokens, or raw conversation payloads.

## Frozen check ids

```text
environment.python
environment.package_metadata
environment.extension_id_integrity

auth.file
auth.material
auth.access_token_freshness
auth.browser_profile

install.extension_package
install.native_host_manifest
install.native_host_registration

bridge.available
bridge.extension_connected

runtime.assembly                 # emitted only if assembly itself fails
runtime.health
runtime.fail_closed_policy
runtime.required_capabilities

artifact.manifest                # SKIP when no manifest is requested
artifact.<manifest-filename>     # one check per requested manifest
```

Future schemas may add checks, but existing ids should not silently change meaning.

## Environment and auth semantics

The Python check enforces the package requirement `>=3.10`. Installed package metadata is advisory for source-tree execution, so missing metadata is `WARN`, not `FAIL`.

The extension id is recomputed from the frozen public key and compared with the configured packaged id.

Auth diagnosis uses `get_auth_status()` and never prints credentials. Missing auth or absence of reusable session material is a required failure. An access token due for refresh is a warning because the reusable session path may still be valid; `doctor` does not automatically refresh it. The persistent browser profile is advisory for future interactive reauthorization.

## Native install and bridge semantics

The install section verifies:

- packaged extension directory and `manifest.json`,
- Native Messaging host manifest presence and JSON validity,
- frozen host name and `stdio` type,
- expected extension origin,
- declared host executable existence,
- platform registration resolving to the expected host manifest.

On Windows, registration is checked through the current-user Chrome Native Messaging registry key. Bridge checks use only `BrowserNativeTurnProvider.status()` / ping and never submit a turn.

## Runtime semantics

The runtime section calls only:

```text
runtime.health(...)
runtime.capabilities()
```

No send method is called.

The fail-closed policy check requires:

```text
automatic_write_retry = false
fallback_transport     = null
```

The required CWA 0.2 capability set is:

```text
text_turns
new_chat
continuation
conversation_read
conversation_status
model_selection
streaming
temporary_chat
```

Every one must report `AVAILABLE` through the existing evidence-backed capability surface.

`--conversation <id-or-url>` optionally adds canonical status to the health check for a durable conversation. Doctor does not attach/reopen or write to it.

## Artifact verification

PR8.16 verifies one or more PR8.15 manifests:

```powershell
cwa doctor --artifact .\artifact.manifest.json
cwa doctor --artifact .\a.manifest.json --artifact .\b.manifest.json --json
```

For each manifest it checks:

- JSON object and schema `1`,
- supported artifact kind and exact kind/contract pairing,
- non-empty conversation id and positive artifact index,
- export/snapshot format semantics,
- non-empty file list,
- manifest-relative safe basename paths on every OS,
- required/unique file roles,
- emitted file existence,
- exact byte count,
- lowercase SHA-256 syntax,
- exact SHA-256 over bytes currently on disk.

The verifier reads only; it does not repair or rewrite a damaged bundle. If no `--artifact` is supplied, `artifact.manifest` is `SKIP`.

## Regression evidence

User-reported regression on Windows / Python 3.14.6:

```text
focused doctor regression             15 passed in 0.22s
relevant diagnostics/runtime suite    46 passed in 0.35s
full repository suite               1273 passed in 23.16s
```

All three gates passed with no failures.

## Read-only production evidence

### Default environment preflight

```powershell
cwa doctor --json
```

Result:

```text
ok    = true
PASS  = 15
WARN  = 0
FAIL  = 0
SKIP  = 1   # artifact verification not requested
```

Observed environment/install/runtime facts included:

```text
Python                         = 3.14.6
package metadata               = 0.1.7
extension-id integrity         = PASS
auth file/material             = PASS
Native Messaging manifest      = PASS
Windows registry registration  = PASS
bridge reachable               = PASS
extension connected            = PASS
runtime ready                  = PASS
automatic_write_retry          = false
fallback_transport             = null
required CWA 0.2 capabilities  = AVAILABLE
```

No product write was performed.

### PR8.15 artifact integrity

Two previously-created PR8.15 manifests were checked in one doctor run:

```text
conversation export:
  artifact_kind = conversation_export
  contract      = normalized_current_branch_export_v1
  format        = jsonl
  bytes         = 5563
  sha256        = f9e0986015b315efc47dd707ff58b0341c039dd549ab8f41d38e29f2910d375b

conversation snapshot:
  artifact_kind = conversation_snapshot
  contract      = curated_current_branch_context_v1
  format        = null
  bytes         = 1876
  sha256        = 7892e2138500bffc0fdbe50d1db41288bb0b2d60375b16c70ec0e9df50570ca6
```

Doctor result:

```text
ok    = true
PASS  = 17
WARN  = 0
FAIL  = 0
SKIP  = 0
```

Both manifests and their emitted bytes were internally consistent.

### Conversation-scoped canonical health

A durable conversation was checked through:

```powershell
cwa doctor --conversation <durable-conversation-id> --json
```

Observed:

```text
canonical_read_checked = true
canonical_status       = completed
runtime.ready          = true
automatic_write_retry  = false
fallback_transport      = null
```

Report summary remained:

```text
ok    = true
PASS  = 15
WARN  = 0
FAIL  = 0
SKIP  = 1
```

Again, no product write was performed.

## Closure decision

All PR8.16 graduation conditions are satisfied:

```text
focused doctor regression             PASS
relevant diagnostics/runtime suite    PASS
full repository suite                 PASS
live environment doctor               PASS
Windows Native Messaging diagnosis    PASS
PR8.15 artifact verification          PASS
conversation-scoped canonical health  PASS
product writes performed by doctor    0
runtime retry/fallback policy          false / null
```

**PR8.16 is CLOSED / PASS.**
