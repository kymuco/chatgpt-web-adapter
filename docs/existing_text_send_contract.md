# Existing-Conversation Ordinary-Text Write Contract

PR7.11a integrates the live-observed ChatGPT Web prepare/conduit contract into
ordinary text writes to an **existing** conversation.

The scope is deliberately narrow. New-chat sends and multimodal sends keep their
previous transport until they receive independent live-contract evidence.

## Write sequence

For `send_to_conversation(..., media=None)` the adapter now performs:

```text
build one user message
  -> POST /backend-api/f/conversation/prepare
       partial_query.id == final messages[0].id
       x-conduit-token: no-token
  -> require successful prepare + conduit token
  -> POST /backend-api/sentinel/chat-requirements
       existing PoW / Turnstile governance remains in force
  -> POST /backend-api/f/conversation
       client_prepare_state: success
       x-conduit-token: <prepare token>
       x-oai-turn-trace-id: <fresh UUID>
       x-openai-target-path: /backend-api/f/conversation
       x-openai-target-route: /backend-api/f/conversation
```

The conduit token is retained only in memory. Sanitized debug traces continue to
redact `x-conduit-token`, and emitted lifecycle events expose only token-presence
booleans.

## Failure boundaries

The final conversation write must not occur when:

- prepare is rejected;
- prepare succeeds without a conduit token;
- chat requirements do not return a token;
- the existing Turnstile gate requires browser-derived evidence that is absent.

A successful prepare does not weaken the challenge boundary. It only establishes
the short-lived transport material required by the current web write contract.

## Streaming and recovery

The prepared write reuses the existing backend streaming parser. If the initial
stream/handoff does not yield a usable assistant message, the adapter performs a
bounded existing-conversation poll using the already-known parent message as the
recovery boundary.

## Explicit non-goals

PR7.11a does not characterize or change:

- `ChatGPTWebClient.send()` for a new conversation;
- existing-conversation sends containing media;
- Turnstile acquisition or bypass;
- the WebSocket capability contract planned for PR7.12.

## Live validation

After CI, run the existing privacy-safe live contract probe against a current
conversation. Because that probe calls `send_to_conversation()`, a successful
write now validates the integrated prepare/conduit path as well as model and
reasoning preservation.

```powershell
python .\examples\probe_live_contract.py `
  "https://chatgpt.com/c/<conversation-id>" `
  --output .\gpt56-live-write.json
```

A Turnstile-gated result remains a valid safety outcome: prepare can succeed and
the final write must still stop before `/backend-api/f/conversation` when the
required browser challenge evidence is unavailable.
