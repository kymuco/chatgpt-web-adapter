# Release Checklist

Use this checklist before cutting a release or publishing a new package version.

## Tests

- Run the full test suite:
  - `pytest -q`
- Build release artifacts:
  - `python -m build`
- Validate package metadata:
  - `python -m twine check dist/*`
- Smoke test the built wheel in a clean environment:
  - `python -m pip install --force-reinstall dist/*.whl`
  - `python -c "from webchat_adapter import ChatGPTWebClient"`
- If public exports changed, recheck API-surface tests.
- If transport/parsing changed, recheck client/status/message tests.

## Documentation

- README reflects current stable vs experimental boundaries.
- USAGE reflects current public exports and behavior.
- New user-facing features or limitations are documented.
- Experimental features are still clearly marked as experimental.

## Live Verification

- Run the stable-core items from [live_smoke_checklist.md](./live_smoke_checklist.md)
- Re-run experimental approval checks only if:
  - approval code changed, or
  - connector/web approval behavior appears to have changed

## Repository Hygiene

- No secrets or traffic traces are staged.
- `auth_data.json` and local scan artifacts remain untracked.
- Commit history is clean and logically grouped.

## Versioning and Notes

- Update changelog or release notes if applicable.
- Call out compatibility-impacting changes explicitly.
- Mention any known live-site caveats discovered during smoke testing.

## Exit Criteria

- Tests pass.
- Build artifacts pass `twine check`.
- Built wheel installs and imports cleanly.
- Stable-core live smoke passes.
- Docs are in sync with behavior.
- Experimental caveats are still explicit.
