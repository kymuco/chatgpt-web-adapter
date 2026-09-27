# Using CWA from Local Assistants and Agents

CWA is useful below an agent.

The agent decides **what should be attempted**. CWA provides bounded access to hosted
product capabilities and preserves product/write/finality uncertainty.

```text
local assistant / coding agent / swarm
                |
                v
          tool wrapper
                |
                v
               CWA
                |
                v
      hosted consumer product
```

## What exists today

Supported integration choices today:

1. call the Python runtime/capability directly;
2. invoke the stable `cwa` CLI from a local tool runner;
3. build a thin application-owned adapter around one exact CWA capability.

A dedicated MCP adapter is **not shipped yet**.

## Python tool wrapper - ChatGPT

```python
from chatgpt_web_adapter import assemble_product_runtime

runtime = assemble_product_runtime(
    transport="browser-owned",
    auth_file="auth_data.json",
)

def ask_chatgpt(prompt: str) -> str:
    execution = runtime.send_text_observed(prompt)
    return execution.response.text
```

Your agent should still decide whether this tool may be called. CWA does not treat tool
availability as user approval.

## Python tool wrapper - translation

```python
from chatgpt_web_adapter.google_translate_web import GoogleTranslateWebCapability

translator = GoogleTranslateWebCapability()

def translate_text(text: str, source: str, target: str) -> str:
    result = translator.translate_text(
        text,
        source_language=source,
        target_language=target,
    )
    return result.translated_text
```

The translation surface is experimental and page-finality is noncanonical.

## CLI tool wrapper

For a minimal local agent that can launch subprocesses:

```bash
cwa doctor --json
cwa capabilities --json
cwa send "Summarize this task in three bullets." --profile HIGH
```

Treat structured exit/failure classes as part of the tool contract. In particular,
reconciliation-required output must not be converted into automatic replay.

## Agent-side policy that remains outside CWA

CWA intentionally does not own:

- task planning;
- autonomous continuation;
- budget policy;
- user approval;
- filesystem/Git/workspace authority;
- provider failover policy;
- retry of ambiguous product writes.

A useful composition is:

```text
agent policy
-> decide whether capability may run
-> CWA executes one bounded product operation
-> agent receives result/provenance/failure
-> agent decides the next step
```

## Toward MCP

An MCP adapter is a strong future adoption layer because it can expose CWA capabilities
to existing local-agent ecosystems without moving orchestration into CWA.

It should be built **on top of** proven CWA contracts.

A future shape may look like:

```text
agent
-> MCP
-> CWA adapter
-> exact product capability
```

Do not introduce a generic MCP capability catalog before CWA has enough independent
non-chat evidence to know what the common contract really is.

## Recommended agent discovery

Start with:

- [Quickstart](quickstart.md);
- [Capability map](capabilities.md);
- [Architecture](architecture.md);
- [Security](../SECURITY.md);
- repository-root [`llms.txt`](../llms.txt).
