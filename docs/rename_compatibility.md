# Rename Compatibility Plan

This project may later move to the clearer public name `chatgpt-web-adapter`, with the Python import package `chatgpt_web_adapter`.

The rename is planned for a future milestone. It is not implemented today.

## Current Name

Today, only the current package exists:

- Repository: `webchat-adapter`
- Distribution package: `webchat-adapter`
- Python import package: `webchat_adapter`

Current supported import:

```python
from webchat_adapter import ChatGPTWebClient
```

## Future Name

The future naming target is:

- Repository: `chatgpt-web-adapter`
- Distribution package: `chatgpt-web-adapter`
- Python import package: `chatgpt_web_adapter`

Future preferred import:

```python
from chatgpt_web_adapter import ChatGPTWebClient
```

That future import is not available yet.

## Compatibility Import

The existing `webchat_adapter` import path will remain the compatibility import after the future rename:

```python
from webchat_adapter import ChatGPTWebClient
```

The compatibility import should remain available for multiple minor releases after the new package exists.

## Policy

- Do not rename before the SDK has enough user-facing value.
- Do not rename before the early value milestones are complete.
- Keep `webchat_adapter` as the old compatibility import after the future rename.
- Do not remove `webchat_adapter` without a documented deprecation period.
- Do not add deprecation warnings until `chatgpt_web_adapter` exists and migration is actually possible.
- Do not update examples to `chatgpt_web_adapter` before the new import exists.

## Migration Phases

### Phase 0 - Current

Only `webchat_adapter` exists. Documentation and examples must continue to use:

```python
from webchat_adapter import ChatGPTWebClient
```

### Phase 1 - Dual Import

After the future rename package is introduced, both imports should work:

```python
from chatgpt_web_adapter import ChatGPTWebClient
from webchat_adapter import ChatGPTWebClient
```

At this phase, `webchat_adapter` should be a thin compatibility layer around the new package.

### Phase 2 - Preferred New Import

Documentation and new examples may move to:

```python
from chatgpt_web_adapter import ChatGPTWebClient
```

The old `webchat_adapter` import should remain supported.

### Phase 3 - Long-Term Compatibility

Keep `webchat_adapter` as a compatibility import unless the maintenance cost becomes unreasonable.

If removal is ever considered, it should require:

- a release note;
- a deprecation warning period;
- a migration guide;
- enough time for downstream users to update imports.

## Out of Scope for the Current Milestone

This plan does not rename the repository, package, distribution metadata, source directory, examples, or documentation imports.

For now, use `webchat_adapter`.
