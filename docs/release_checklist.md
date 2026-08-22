# Release Checklist

Use this checklist before cutting a GitHub release or publishing a package version.

PR8.17 separates two moments:

```text
release candidate ready
        !=
package published
```

Merging release-hardening code never grants permission to publish. A tagged PyPI release is a separate action.

## 1. Regression

Run the focused release-hardening tests:

```powershell
python -m pytest tests/test_release_hardening_pr8_17.py -q
```

Run the relevant packaging/CLI/doctor/artifact tests, then the full repository suite:

```powershell
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

The gate validates:

- static package version from `pyproject.toml`;
- exactly one wheel and one sdist;
- canonical distribution filenames;
- wheel `Name` / `Version` metadata;
- `cwa`, `chatgpt-web-adapter`, and native-host console entry points;
- required 0.2 modules;
- all packaged browser-extension `.json` / `.js` files from the source package-data set;
- required sdist source/package files.

This candidate gate does not require a Git tag.

## 4. Installed-wheel smoke

Test the exact built wheel, not an editable checkout:

```powershell
python tools/installed_wheel_smoke.py `
  --wheel-dir dist `
  --expected-version 0.2.0 `
  --json
```

The smoke installs the wheel through `pip --no-deps --force-reinstall` and verifies:

- import resolves from `site-packages`, not the repository `src/` tree;
- installed package metadata reports the expected version;
- `cli_v02`, `doctor`, and artifact-manifest modules exist;
- all three console scripts are installed with the frozen targets;
- `cwa --help` and the stable 0.2 command help surfaces execute successfully;
- the installed browser-extension directory contains the required package data;
- `cwa doctor` can diagnose a deliberately unconfigured/missing-auth environment as structured unavailable (`exit 1`) rather than crashing;
- static installed-package doctor checks remain `PASS`.

CI runs this installed-wheel smoke on Linux and Windows with Python 3.10 and 3.14 after the full 3.10-3.14 source-test matrix.

## 5. Live product verification

For a release that contains product-runtime behavior changes, rerun the appropriate live evidence gates.

For the CWA 0.2 release candidate after PR8.17, the already-proven baseline includes:

```text
cwa doctor                PASS
cwa status                PASS
cwa capabilities          PASS
HIGH alias product write  PASS
messages                  PASS
snapshot/export manifests PASS
doctor artifact verify    PASS
Temporary / streaming / model-selection production gates preserved
```

PR8.17 itself must not add or modify a product write path.

## 6. Version and changelog finalization

Before creating `vX.Y.Z`:

1. `pyproject.toml` must contain exactly `X.Y.Z`.
2. `CHANGELOG.md` must contain a dated heading:

   ```text
   ## X.Y.Z - YYYY-MM-DD
   ```

3. The GitHub release tag must be exactly `vX.Y.Z` (the checker also accepts a raw `X.Y.Z` input for local verification).

Validate the strict tagged contract locally before publishing:

```powershell
python tools/release_gate.py `
  --dist-dir dist `
  --tag v0.2.0 `
  --json
```

A tag/version mismatch or missing dated changelog entry fails before upload.

## 7. Repository hygiene

Before tagging:

- `git status` is clean;
- no auth/session files are tracked;
- no HAR/traffic traces, browser profiles, local artifacts, or private prompts were added;
- release artifacts came from the intended commit;
- CI is green for that exact commit;
- the release notes describe user-visible changes and known limitations.

## 8. Publishing

PyPI publishing is triggered only by a published GitHub Release and uses Trusted Publishing.

The publish workflow rebuilds the distributions and reruns, in order:

```text
python -m build
python -m twine check dist/*
strict tagged release gate
installed exact-wheel smoke
PyPI Trusted Publishing upload
```

If any pre-upload step fails, publishing stops.

## 9. Post-publish verification

After PyPI reports the version:

1. create a new clean environment;
2. install the public artifact from PyPI, not the repository;
3. verify package version;
4. run `cwa --help`;
5. run `cwa doctor --json` before and after normal local setup;
6. verify the packaged extension directory exists;
7. perform one controlled product smoke if the release policy calls for it.

Only then should downstream projects such as CMA pin the released CWA version.

## Exit criteria

```text
focused release regression         PASS
relevant regression                PASS
full repository regression         PASS
Linux/Windows Python 3.10-3.14 CI  PASS
wheel + sdist build                PASS
twine metadata check               PASS
candidate release gate             PASS
installed-wheel smoke              PASS
tag/version/changelog contract     PASS before publication
PyPI post-publish install          PASS after publication
```
