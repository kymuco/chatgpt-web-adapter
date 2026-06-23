# Package Naming

The package rename is complete.

Canonical naming is now:

- Repository: `chatgpt-web-adapter`
- Distribution package: `chatgpt-web-adapter`
- Python import package: `chatgpt_web_adapter`

Supported import:

```python
from chatgpt_web_adapter import ChatGPTWebClient
```

The old `webchat_adapter` import is intentionally not supported anymore.

## Policy

- New documentation and examples must use `chatgpt_web_adapter`.
- New code should not reference `webchat_adapter`.
- If old snippets or notes are found, they should be updated rather than preserved as compatibility guidance.

## Scope

This rename includes:

- package metadata
- source directory naming
- examples
- documentation imports
- test imports

It does not change the public SDK class and helper names such as `ChatGPTWebClient`, `PayloadBuilder`, or `RequestError`.
