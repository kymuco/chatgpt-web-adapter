# Live Smoke Checklist

Use this checklist when `chatgpt.com` behavior may have changed or before a release that touches transport, parsing, uploads, or approval helpers.

## Safety and Hygiene

- Use a valid local `auth_data.json` that is not committed to the repository.
- Store local traffic artifacts outside tracked files or in a locally excluded directory such as `traffic-scan/`.
- Sanitize tokens, cookies, and proof/turnstile headers before sharing traces.
- Prefer harmless prompts and disposable test conversations.
- For approval testing, prefer low-risk test workspaces or disposable connector targets.

## Core Stable Scenarios

### 1. New Chat Send

- Send a simple prompt such as `Reply with exactly: smoke-ok`
- Confirm:
  - request completes successfully
  - streamed text is correct
  - `conversation_id` is returned
  - `finish_reason` is parsed
- If broken, inspect:
  - `chat-requirements`
  - send payload shape
  - SSE event format

### 2. Continue Existing Conversation

- Continue a known conversation with `send_to_conversation()`
- Confirm:
  - conversation id is preserved
  - parent message resolution still works
  - returned text is correct
- If broken, inspect:
  - conversation payload schema
  - current node / mapping layout
  - model detection assumptions

### 3. Attach / Read / Status

- Run `attach_conversation()`
- Run `get_messages()`
- Run `get_status()`
- Confirm:
  - latest message selection still works
  - message text extraction is sane
  - status / finish reason are correct
- If broken, inspect:
  - conversation `mapping`
  - message `content`
  - metadata and approval signals

### 4. Image Upload

- Send a tiny PNG with a simple prompt
- Confirm:
  - file creation succeeds
  - upload succeeds
  - multimodal request succeeds
  - assistant reply completes normally
- If broken, inspect:
  - `/backend-api/files`
  - upload/finalize flow
  - attachment metadata
  - multimodal message structure

## Experimental Scenarios

### 5. Approval Flow

- Run only if approval helpers are relevant to current work.
- Use a low-risk, disposable connector target.
- Confirm:
  - pending approval is detected
  - prepare request succeeds
  - approval resume turn is accepted
  - a new assistant message appears after approval
- If broken, inspect:
  - pending approval descriptor shape
  - prepare payload and headers
  - approval stream payload
  - post-approval polling behavior

## What to Save When Something Breaks

- request URL and method
- response status
- sanitized request headers
- sanitized request body
- response JSON body when applicable
- raw SSE event sequence when applicable
- exact SDK method used
- exact exception text

## Suggested Debugging Order

1. Auth and token freshness
2. `chat-requirements`
3. send payload shape
4. SSE parsing
5. conversation payload parsing
6. upload flow
7. approval flow

## Exit Criteria

- Stable core scenarios pass before release.
- Experimental scenarios are rechecked when touched or when there is evidence the site changed.
