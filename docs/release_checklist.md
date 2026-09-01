# Release Checklist

Use this checklist before cutting a GitHub release or publishing a package version.

CWA keeps two moments separate:

```text
release candidate ready
        !=
package published
```

Merging release-hardening code never grants permission to publish. A tagged PyPI release is a separate explicit action.

## 1. Regression

Run the focused release-surface tests and then the full repository suite:

```powershell
python -m pytest tests/test_release_hardening_pr8_17.py tests/test_release_surface_pr9_4.py -q
python -m pytest -q
```

No release may proceed with a failing test.

## 2. Build exact distributions

Start from a clean `dist/` directory:

```powershell
Remove-Item -Recurse -Force .\dist -ErrorAction SilentlyContinue
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

The release candidate must produce exactly one wheel and one sdist.

## 3. Candidate artifact contract

Run:

```powershell
python tools/release_gate.py --dist-dir dist --json
```

The candidate gate validates:

- static package version from `pyproject.toml`;
- exactly one wheel and one sdist;
- canonical distribution filenames;
- wheel `Name` / `Version` metadata;
- `cwa`, `chatgpt-web-adapter`, and native-host console entry points;
- frozen product-runtime, transport, capability, provenance, observation and public-surface modules required by the 0.3 SDK;
- all packaged browser-extension `.json` / `.js` files from the source package-data set;
- required sdist source/package files, including root `CHANGELOG.md`.

This candidate gate does not require a Git tag.

## 4. Installed-wheel smoke

Test the exact built wheel, not an editable checkout:

```powershell
python tools/installed_wheel_smoke.py `
  --wheel-dir dist `
  --json
```

When `--expected-version` is omitted, candidate smoke derives the expected static `[project].version` from the checkout `pyproject.toml`. The publish workflow passes the release tag explicitly and therefore remains stricter.

The smoke installs the wheel through `pip --no-deps --force-reinstall` and verifies:

- import resolves from `site-packages`, not the repository `src/` tree;
- installed package metadata reports the expected version;
- frozen CWA 0.3 product-runtime modules are importable from the installed package;
- root `PRIMARY_PRODUCTION` observation value types are present;
- `MediaItem` / `MediaSource` retain `SHARED_SUPPORT` classification;
- the internal `ProductObservationCollector` does not leak into the root public API;
- all three console scripts are installed with the frozen targets;
- `cwa --help` and the stable command help surfaces execute successfully;
- the installed browser-extension directory contains the required package data;
- `cwa doctor` can diagnose a deliberately unconfigured/missing-auth environment as structured unavailable (`exit 1`) rather than crashing;
- static installed-package doctor checks remain `PASS`.

CI runs this installed-wheel smoke on Linux and Windows with Python 3.10 and 3.14 after the full Python 3.10-3.14 source-test matrix on both operating systems.

## 5. Live product verification

A release does not need fresh product writes merely because documentation, packaging or version metadata changed. Live gates are required when the release candidate changes product-facing behavior that is not already covered by bounded evidence on the same implementation path.

The CWA 0.3 production evidence baseline includes:

```text
browser-owned text new chat / continuation    PASS
canonical readback finality                   PASS
revision-safe streaming                       PASS
Temporary Chat                                PASS
model/reasoning selection baseline            PASS
PR9.2 image new chat                          PASS
PR9.2 general file new chat                   PASS
PR9.2 multimodal continuation                 PASS
PR9.2 exact attachment/request correlation    PASS
PR9.3 web-search observation                  PASS
PR9.3 source/citation relationship evidence   PASS
PR9.3 generic product-tool observation        PASS
no automatic ambiguous-write retry            PASS
fallback transport                            NONE
```

Capability declarations must remain narrower than the evidence. In particular, `tools_connectors` remains `UNKNOWN`, and `browserless-request` remains `EXPERIMENTAL`.

## 6. Version and changelog finalization

Before creating `vX.Y.Z`:

1. `pyproject.toml` must contain exactly `X.Y.Z`.
2. `CHANGELOG.md` must contain a dated heading:

   ```text
   ## X.Y.Z - YYYY-MM-DD
   ```

3. The GitHub release tag must be exactly `vX.Y.Z` (the checker also accepts a raw `X.Y.Z` input for local verification).

Validate the strict tagged contract locally before publishing. For CWA 0.3.0:

```powershell
python tools/release_gate.py `
  --dist-dir dist `
  --tag v0.3.0 `
  --json
```

A tag/version mismatch or missing dated changelog entry fails before upload.

## 7. Repository hygiene

Before tagging:

- `git status` is clean;
- no auth/session files are tracked;
- no HAR/traffic traces, browser profiles, local artifacts, private prompts or credential-bearing source URLs were added;
- release artifacts came from the intended exact commit;
- CI is green for that exact commit;
- release notes describe user-visible changes, support tiers and known limitations;
- no unresolved release-blocking review thread remains.

## 8. Publishing

PyPI publishing is triggered only by a published GitHub Release and uses Trusted Publishing.

The publish workflow rebuilds the distributions and reruns, in order:

```text
python -m build
python -m twine check dist/*
strict tagged release gate
installed exact-wheel smoke with release tag
PyPI Trusted Publishing upload
```

If any pre-upload step fails, publishing stops.

## 9. Post-publish verification

After PyPI reports the version:

1. create a new clean environment;
2. install the public artifact from PyPI, not the repository;
3. verify package version;
4. run `cwa --help`;
5. import the frozen primary product-runtime/observation surface;
6. run `cwa doctor --json` before and after normal local setup;
7. verify the packaged extension directory exists;
8. perform one controlled product smoke only if the release policy calls for it.

Only then should downstream projects pin the released CWA version.

## Exit criteria

```text
focused release regression          PASS
full repository regression          PASS
Linux/Windows Python 3.10-3.14 CI   PASS
wheel + sdist build                 PASS
twine metadata check                PASS
candidate release gate              PASS
installed-wheel smoke               PASS
frozen 0.3 public surface           PASS
tag/version/changelog contract      PASS before publication
PyPI post-publish install           PASS after publication
```
