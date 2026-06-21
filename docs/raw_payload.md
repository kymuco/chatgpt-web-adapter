# Raw Payload Experimental API

> [!WARNING]
> This is an experimental raw ChatGPT web backend API.
> It is not an official OpenAI API and not a stable backend contract.
> The ChatGPT web backend may change at any time.
> `send_payload()` sends real requests and can create real ChatGPT web conversations/messages.
> Use it only when you intentionally need raw-payload experiments.
> Use at your own risk.

The raw payload API is an advanced escape hatch for users who need to build,
inspect, modify, validate, and send ChatGPT web backend payload dictionaries.
It is not the normal way to send messages.

Use `send()` for ordinary chat requests. Use `send_payload()` only when you
intentionally need raw backend payload control.

## What this API is for

Raw payload helpers are useful for:

- experimenting with captured ChatGPT web payloads
- comparing SDK-built payloads with browser-built payloads
- testing new top-level backend fields before high-level SDK support exists
- debugging adapter, agent-runtime, or transport behavior
- building controlled research tooling around web payload shape changes

## What this API is not for

Do not treat this API as:

- the recommended default way to send chat messages
- a stable production contract
- a replacement for `send()`
- a replacement for the official OpenAI API
- a way to bypass approval policy helpers
- a complete schema-validated backend client

## Basic workflow

Start with `PayloadBuilder`, optionally modify the payload, validate obvious
top-level fields, and then send the payload.

```python
from webchat_adapter import ChatGPTWebClient, PayloadBuilder, validate_payload

client = ChatGPTWebClient(auth_file="auth_data.json")

payload = PayloadBuilder.new_chat(
    "Say hello in one sentence.",
    model="gpt-4o-mini",
)

validate_payload(payload)
response = client.send_payload(payload)

print(response.text)
```

`PayloadBuilder` creates a reasonable starting point. `validate_payload()`
catches obvious missing top-level fields. `send_payload()` sends the dictionary
as a raw ChatGPT web backend payload.

The SDK does not normalize or repair custom raw fields. If the backend rejects a
modified payload, that is expected for experimental usage.

## PayloadBuilder

`PayloadBuilder` returns plain Python dictionaries. It does not send requests and
it does not promise backend stability.

### Build a new-chat payload

```python
from webchat_adapter import PayloadBuilder

payload = PayloadBuilder.new_chat(
    "Summarize this in one sentence.",
    model="gpt-4o-mini",
    parent_message_id="parent-1",
)
```

A new-chat payload includes fields such as:

- `action`
- `parent_message_id`
- `model`
- `conversation_mode`
- `messages`
- buffering/default fields used by the current SDK transport

These fields mirror the SDK's current high-level payload defaults, but the
ChatGPT web backend can change them at any time.

### Build a continue-chat payload

```python
payload = PayloadBuilder.continue_chat(
    "Continue from here.",
    conversation={
        "conversation_id": "conversation-id",
        "message_id": "latest-message-id",
    },
    model="gpt-4o-mini",
)
```

`continue_chat()` requires a conversation id and a parent message id. It can
resolve the parent id from `conversation["parent_message_id"]` or
`conversation["message_id"]`.

### Build a single text message

```python
message = PayloadBuilder.text_message(
    "Hello",
    role="user",
)
```

`PayloadBuilder.text_message()` builds an outbound raw payload message
dictionary. It is not the same type as `ChatMessage`, which represents messages
read from an existing conversation.

## Custom modifications

The raw payload API exists so advanced users can inspect and modify payloads.
Change one thing at a time and keep logs of backend behavior.

```python
payload = PayloadBuilder.new_chat("Test a custom payload field.")

payload["some_experimental_field"] = {
    "enabled": True,
}

validate_payload(payload)
response = client.send_payload(payload)
```

The SDK will not know whether custom fields are supported. Backend rejection is
part of the experimental workflow.

## validate_payload()

`validate_payload()` performs lightweight validation only. It is not a complete
backend schema validator.

It checks:

- `payload` is a dictionary
- `action` is a non-empty string
- `parent_message_id` is a non-empty string
- `model` is a non-empty string
- `messages` is a non-empty list
- each item in `messages` is a dictionary
- `conversation_id` is optional and may be `None` or a non-empty string

It does not validate:

- message content schema
- author roles
- metadata
- tool payloads
- media payloads
- backend-supported actions
- model availability
- all ChatGPT web backend fields

```python
from webchat_adapter import PayloadValidationError, validate_payload

try:
    validate_payload(payload)
except PayloadValidationError as error:
    print("Bad raw payload:", error)
```

`PayloadValidationError` is raised before any network request when
`send_payload()` receives an obviously malformed raw payload.

## send_payload()

`send_payload()` sends a raw payload dictionary through the existing ChatGPT web
stream transport and returns a normal `ChatResponse`.

```python
response = client.send_payload(
    payload,
    on_token=lambda token: print(token, end="", flush=True),
)

print(response.text)
print(response.conversation.conversation_id)
print(response.conversation.message_id)
```

The method validates the payload, deep-copies it, obtains the current web
backend requirements/proof headers, sends the copied payload through the stream
transport, and returns a `ChatResponse`.

Timing metrics may be less detailed than the high-level `send()` API.

## Events

On successful raw payload transport, `send_payload()` emits a `raw_payload_sent`
event when `on_event` is provided.

```python
events = []

response = client.send_payload(
    payload,
    on_event=events.append,
)

print(events[-1])
```

Example event shape:

```python
{
    "type": "raw_payload_sent",
    "experimental": True,
    "conversation_id": "...",
    "message_id": "...",
    "message_count": 1,
}
```

This is not an approval event. Approval events are part of the separate approval
helper APIs.

## Error handling

```python
from webchat_adapter import PayloadValidationError, RequestError

try:
    response = client.send_payload(payload)
except PayloadValidationError as error:
    print("Bad raw payload:", error)
except RequestError as error:
    print("Backend or transport failed:", error)
```

`PayloadValidationError` happens before network work. `RequestError` can happen
after validation, while preparing requirements/proof headers or during backend
transport.

## Captured browser payloads

Captured browser payloads may include fields the SDK does not create. That is
expected.

For new chats, captured payloads may include:

```python
{"conversation_id": None}
```

The lightweight validator accepts this value. For existing conversations,
`conversation_id` should normally be a non-empty string.

## Recommended workflow

1. Start with `PayloadBuilder.new_chat()` or `PayloadBuilder.continue_chat()`.
2. Print or save the generated payload.
3. Modify one field at a time.
4. Run `validate_payload()`.
5. Call `send_payload()`.
6. Capture `raw_payload_sent` and backend errors.
7. Move repeated successful patterns into high-level SDK APIs only after they
   are stable enough to support.

## Non-goals

The raw payload API does not provide:

- full JSON schema validation
- backend compatibility guarantees
- media upload orchestration
- tool approval policy bypass
- durable conversation state
- official OpenAI API compatibility
