# PR8.17 — Packaging / CI / Release Hardening

_Status: CLOSED / PASS — release candidate engineering gate complete_

_Base: `main` after merged PR8.16 (`4d87993f0cce28842a2e645797228b4013c5dc65`)_

## Purpose

PR8.17 is the final engineering hardening step before the CWA 0.2 release gate.

It does not add ChatGPT product capabilities. It makes the already-proven CWA 0.2 surface reproducibly buildable, installable, inspectable, and publishable.

The target chain is:

```text
source checkout works
        ↓
full tests pass
        ↓
wheel + sdist build
        ↓
release artifact contract passes
        ↓
exact wheel installs into disposable clean venv
        ↓
installed CLI/package-data/doctor smoke passes
        ↓
strict tag/version/changelog gate passes
        ↓
Trusted Publishing may upload
```

## Scope boundary

PR8.17 changes packaging/release surfaces only:

- `pyproject.toml` version metadata;
- CI build and installed-wheel smoke;
- PyPI publish pre-upload gates;
- repository-local release tools;
- README/release checklist;
- release-hardening regression tests.

It must not change:

```text
ProductWriteTransport
BrowserOwnedProductTransport
Temporary Chat semantics
streaming semantics
model selector behavior
canonical readback/finality
Browser Authority lifecycle
retry/fallback policy
snapshot/export schema
doctor classification semantics
```

## Version staging

`pyproject.toml` is staged at:

```text
0.2.0
```

This does not publish the package.

The release process deliberately separates:

```text
PR8.17 merged / release candidate ready
        !=
GitHub Release v0.2.0 published
        !=
PyPI upload verified
```

The current changelog may remain without a dated `0.2.0` heading while PR8.17 is only a candidate. The strict tagged release gate requires a final dated heading before a release can publish:

```text
## 0.2.0 - YYYY-MM-DD
```

## Candidate release gate

Repository-local tool:

```powershell
python tools/release_gate.py --dist-dir dist --json
```

The candidate gate validates:

- static package version from `[project]`;
- exactly one wheel and one sdist;
- canonical distribution filenames;
- wheel distribution name/version metadata;
- exact console-script mapping;
- required 0.2 modules;
- required browser-extension package data;
- **all** source `browser_native_extension/*.json` and `*.js` files are present in the wheel;
- required source/package files are present in the sdist.

The release tool is repository-local and is not part of the installed SDK package.

## Strict tagged release gate

For a release tag:

```powershell
python tools/release_gate.py `
  --dist-dir dist `
  --tag v0.2.0 `
  --json
```

The gate additionally requires:

```text
normalized tag == pyproject version
CHANGELOG has exact version heading
CHANGELOG heading has YYYY-MM-DD release date
```

Therefore a GitHub Release cannot accidentally publish a mismatched or unfinished version.

## Exact installed-wheel smoke

Repository-local tool:

```powershell
python tools/installed_wheel_smoke.py `
  --wheel-dir dist `
  --expected-version 0.2.0 `
  --json
```

The tool:

1. creates a disposable temporary virtual environment;
2. installs the exact built wheel with `pip --no-deps --force-reinstall`;
3. removes `PYTHONPATH` for the child smoke;
4. executes installed checks from a temporary working directory rather than the repository;
5. destroys the temporary environment after completion.

This prevents an editable source checkout from masking a broken wheel and prevents the release smoke from mutating the developer's active virtual environment.

### Installed assertions

The smoke requires:

```text
installed metadata version matches expected version
package import resolves from site-packages
cli_v02.main exists
doctor.run_doctor exists
artifact manifest schema exists
packaged extension manifest exists
packaged service_worker.js exists
installed extension contains JavaScript package data
```

It freezes the installed console targets:

```text
cwa                             -> chatgpt_web_adapter.cli_v02:main
chatgpt-web-adapter             -> chatgpt_web_adapter.cli_v02:main
chatgpt-web-adapter-native-host -> chatgpt_web_adapter.browser_native_host:main
```

It executes read-only help smoke for:

```text
cwa --help
chatgpt-web-adapter --help
cwa doctor --help
cwa status --help
cwa capabilities --help
cwa messages --help
cwa snapshot --help
cwa export --help
cwa send --help
```

Finally it runs installed `cwa doctor` with a deliberately missing auth path. The expected result is:

```text
exit = 1
schema = 1
command = doctor
ok = false
```

while these installed-package checks must still be `PASS`:

```text
environment.python
environment.package_metadata
environment.extension_id_integrity
install.extension_package
```

and `auth.file` must be classified `FAIL` rather than causing an exception.

This proves that a new user can install the wheel and receive structured setup diagnostics before configuring CWA.

## CI hardening

Source regression remains a Linux/Windows matrix across Python:

```text
3.10
3.11
3.12
3.13
3.14
```

CI invokes the suite through:

```text
python -m pytest -q
```

so repository-local release tooling is imported under the same module-search contract used by the documented local release gate, without turning `tools/` into installed SDK package data.

After all source tests pass, CI builds exactly one release artifact set and runs:

```text
python -m build
python -m twine check dist/*
python tools/release_gate.py --dist-dir dist
```

The exact built distributions are uploaded as one short-lived CI artifact.

A downstream installed-wheel matrix downloads those exact bytes and runs the disposable installed-wheel smoke on:

```text
Ubuntu  + Python 3.10
Ubuntu  + Python 3.14
Windows + Python 3.10
Windows + Python 3.14
```

The boundary versions are chosen for the cross-platform installed-artifact gate while the full source regression continues to cover every supported Python version.

## Publish hardening

PyPI publishing still uses GitHub Release + Trusted Publishing.

Before `pypa/gh-action-pypi-publish` is allowed to run, the publish workflow performs:

```text
build wheel + sdist
twine check
strict tagged release gate
exact installed-wheel smoke
```

The upload step is last. Any mismatch or installed-wheel failure stops publishing before credentials are used for upload.

## README / user-facing boundary

The README preserves the existing proven public-surface tiers, compatibility/research discoverability, examples, raw-payload docs, and browser-native setup while adding the stable 0.2 `cwa` path:

```text
cwa doctor
cwa status
cwa capabilities
cwa send
cwa messages
cwa snapshot
cwa export
```

The README also explicitly preserves:

```text
INSTANT <-> FAST
MEDIUM  <-> BALANCED
HIGH    <-> DEEP
```

and states that image/file upload, multimodal continuation, tools/connectors, and future browserless write transports are later capability work rather than implied 0.2 support.

## Final evidence

Local regression:

```text
focused release hardening             13 passed in 0.28s
relevant 0.2 CLI/artifact/doctor      50 passed in 0.50s
README/docs compatibility repair      26 passed in 0.17s
full repository suite               1286 passed in 23.02s
```

Local distribution build:

```text
chatgpt_web_adapter-0.2.0.tar.gz                 BUILT
chatgpt_web_adapter-0.2.0-py3-none-any.whl       BUILT
twine check wheel                                 PASS
twine check sdist                                 PASS
```

Candidate release gate:

```text
schema                   = 1
ok                       = true
project                  = chatgpt-web-adapter
version                  = 0.2.0
tag                      = null
changelog_release_date   = null
wheel extension files    = 50
console entry points     = 3
```

The null tag/date are intentional at candidate stage; strict tagged publication remains fail-closed until release finalization.

Local disposable installed-wheel smoke:

```text
schema                  = 1
ok                      = true
version                 = 0.2.0
entry points            = 3
help commands           = 9
package provenance      = disposable venv site-packages
extension provenance    = installed wheel site-packages
pre-setup doctor exit   = 1
```

GitHub Actions run `195` on the corrected PR head proved:

```text
Ubuntu  Python 3.10  PASS
Ubuntu  Python 3.11  PASS
Ubuntu  Python 3.12  PASS
Ubuntu  Python 3.13  PASS
Ubuntu  Python 3.14  PASS
Windows Python 3.10  PASS
Windows Python 3.11  PASS
Windows Python 3.12  PASS
Windows Python 3.13  PASS
Windows Python 3.14  PASS
build / twine / candidate artifact gate / upload artifact  PASS
cross-platform exact installed-wheel stage                 PASS
workflow conclusion                                        success
```

An earlier Actions attempt exposed that calling the `pytest` console script did not put repository-local `tools/` on the import path. The CI runner was intentionally aligned with the documented/local `python -m pytest -q` invocation; no SDK package-data expansion was used to hide the issue.

No live ChatGPT product write was required or performed by PR8.17.

## Closure condition

PR8.17 closes with:

```text
focused release regression             PASS
relevant 0.2 CLI/artifact/doctor gate  PASS
full repository suite                  PASS
wheel build                             PASS
sdist build                             PASS
twine check                             PASS
candidate release gate                 PASS
local disposable installed-wheel smoke PASS
CI source matrix                        PASS
CI cross-platform installed-wheel gate PASS
no product-runtime behavioral diff     CONFIRMED
```

After merge, CWA 0.2 still requires a separate explicit release decision, changelog finalization, strict tagged gate, GitHub Release, PyPI post-publish install verification, and then downstream version pinning.
