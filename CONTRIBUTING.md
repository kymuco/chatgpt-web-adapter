# Contributing

Thanks for contributing to `webchat-adapter`.

This repository is intentionally small and should stay disciplined. Changes should preserve the distinction between the stable SDK core and experimental features built on top of changing `chatgpt.com` behavior.

## Development Setup

```bash
python -m pip install -e .[test]
pytest -q
```

## Contribution Expectations

- Keep changes narrowly scoped.
- Prefer preserving existing public API behavior unless a change is clearly justified.
- Do not silently promote experimental behavior into the stable core.
- Add or update tests for any behavior change.
- Update docs when changing public behavior, support level, or operational guidance.

## Stable vs Experimental

Stable-core contributions typically touch:

- send/continue flows
- conversation read/status helpers
- image upload
- auth loading
- transport diagnostics

Experimental contributions typically touch:

- approval helpers
- raw payload helpers
- connector-specific workflow assumptions

Experimental changes should remain clearly labeled as experimental in code and docs.

## Testing

Before opening or finalizing a contribution:

- run `pytest -q`
- if transport/parsing behavior changed, review [docs/live_smoke_checklist.md](./docs/live_smoke_checklist.md)
- if release-impacting behavior changed, review [docs/release_checklist.md](./docs/release_checklist.md)

## Hygiene

- Do not commit `auth_data.json`, tokens, cookies, or local traffic traces.
- Keep traffic artifacts outside tracked files or under a locally excluded path.
- Keep commit history logically grouped. Prefer one commit per completed PR-sized change.
