# Required Actions

ChatGPT web can stop a conversation on UI-only cards that are not normal assistant text and are not browserless tool approvals.

The first supported case is connector OAuth/linking, for example asking a conversation to use Gmail before Gmail is connected. The ChatGPT web UI renders this as a card such as "Connect Gmail" / "Not now". In the raw conversation payload this appears as `jit_plugin_data.from_server.type = "oauth_required"`.

Without explicit detection, SDK consumers can see an empty response or a conversation that appears to stop unexpectedly.

## Inspect a Conversation

Use `get_required_action()` after a send or when inspecting an existing conversation:

```python
from chatgpt_web_adapter import ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")

response = client.send("What is my latest Gmail message?")

if response.conversation.conversation_id:
    action = client.get_required_action(response.conversation)
    if action is not None:
        print(f"required action: {action.type}")
        print(f"reason: {action.reason}")
        print(f"path: {action.path}")
```

For a Gmail connector that is not linked yet, the action may look like:

```python
RequiredAction(
    type="oauth_required",
    reason="missing_link",
    connector_id="connector_...",
    path="/connector_.../search_emails",
    actions=("oauth_redirect", "deny"),
)
```

## What This Does Not Do

`get_required_action()` does not connect Gmail, follow OAuth redirects, or click approval buttons. It only exposes the pending UI state so applications can tell the user what happened.

For CLI tools, the recommended behavior is to print a clear message such as:

```text
The conversation requires connecting Gmail in ChatGPT web.
Open the conversation in the browser and click Connect Gmail, or ask again without Gmail.
```

## Relationship to Tool Approvals

`RequiredAction` is separate from `PendingApproval`.

- `PendingApproval` describes tool execution cards that may be approved browserlessly with experimental approval helpers.
- `RequiredAction` describes UI-only states such as connector OAuth/linking that currently require user action in the web UI.

This surface is experimental because connector card payloads are undocumented and can change with ChatGPT web behavior.
