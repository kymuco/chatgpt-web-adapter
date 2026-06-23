# Rename Compatibility Plan

The repository is now named `chatgpt-web-adapter`. The Python distribution package and import package have not been renamed yet.

The rename is planned for a future milestone. In this document, "the rename" now means the remaining distribution package and Python import package rename, not the already-completed repository rename.

This document tracks the remaining package/import rename plan and the compatibility policy for the existing `webchat_adapter` import.

## Current Name

Today, the repository has the new public name, while the install/import surface remains unchanged:

- Repository: `chatgpt-web-adapter`
- Distribution package: `webchat-adapter`
- Python import package: `webchat_adapter`

Current supported import:

```python
from webchat_adapter import ChatGPTWebClient
```

## Future Name

The future package naming target is:

- Repository: `chatgpt-web-adapter`
- Distribution package: `chatgpt-web-adapter`
- Python import package: `chatgpt_web_adapter`

Future preferred import:

```python
from chatgpt_web_adapter import ChatGPTWebClient
```

That future import is not available yet.

## Compatibility Import

The existing `webchat_adapter` import path will remain the compatibility import after the future package/import rename:

```python
from webchat_adapter import ChatGPTWebClient
```

The compatibility import should remain available for multiple minor releases after the new package exists.

## Policy

- Do not rename the distribution package or import package before the SDK has enough user-facing value.
- Do not rename the distribution package or import package before the early value milestones are complete.
- Keep `webchat_adapter` as the old compatibility import after the future rename.
- Do not remove `webchat_adapter` without a documented deprecation period.
- Do not add deprecation warnings until `chatgpt_web_adapter` exists and migration is actually possible.
- Do not update examples to `chatgpt_web_adapter` before the new import exists.

## Migration Phases

### Phase 0 - Current

The repository is already `chatgpt-web-adapter`, but only `webchat_adapter` exists as an import package. Documentation and examples must continue to use:

```python
from webchat_adapter import ChatGPTWebClient
```

### Phase 1 - Dual Import

After the future import package is introduced, both imports should work:

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

This plan does not rename the distribution package, source directory, examples, documentation imports, or Python import package.

For now, use `webchat_adapter`.