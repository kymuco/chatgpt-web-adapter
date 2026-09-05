# Gemini conversation snapshot probe

Status: **experimental, read-only, protocol probe**.

This experiment checks whether an authenticated ordinary Gemini web conversation can
support the same high-level snapshot workflow that CWA already has for ChatGPT:

```text
conversation URL
      |
      v
provider-owned conversation read
      |
      +--> decoded raw payload (.json)
      +--> normalized user/assistant messages (.json)
      +--> summary-ready context (.md)
```

It intentionally does **not** add Gemini to `ChatGPTProductRuntime`, broaden the
packaged ChatGPT extension permissions, or implement Gemini writes. The purpose is
to prove the canonical-read side first.

## What the probe reads

Gemini's web product currently exposes saved conversation history through its
same-origin batched RPC surface. The history method observed for this purpose is:

```text
RPC: hNvQHb
product: gemini.google.com
operation: list/read conversation turns
```

The probe obtains the current page bootstrap token from the target Gemini
conversation page, calls the read-history RPC from the authenticated browser
origin, and discards the token after the request. Cookies, the bootstrap token,
and request headers are never written to an output artifact.

This is an undocumented web-product contract and can change. The probe therefore
keeps the decoded raw RPC payload as forensic evidence and fails instead of
returning an empty context when the known message shape no longer matches.

## Supported URLs

The initial route parser accepts ordinary private conversation routes:

```text
https://gemini.google.com/app/<chat-id>
https://gemini.google.com/gem/<gem-id>/<chat-id>
https://gemini.google.com/u/<account-index>/app/<chat-id>
https://gemini.google.com/u/<account-index>/gem/<gem-id>/<chat-id>
```

Public `g.co/gemini/share/...` snapshots are a different product surface and are
not part of this probe.

## Run it

1. Open `https://gemini.google.com` in Chrome/Chromium and make sure the account
   that owns the target chat is signed in.
2. Open DevTools -> Sources -> Snippets and create a snippet containing
   `experiments/gemini_conversation_snapshot_probe.js`.
3. Run the snippet once. It installs `window.geminiConversationSnapshot` only in
   the current Gemini page.
4. In the DevTools console run:

```js
await geminiConversationSnapshot(
  "https://gemini.google.com/app/<chat-id>",
  { name: "project" },
)
```

The call is read-only. It downloads:

```text
project_gemini_chat_context.md
project_gemini_chat_messages.json
project_gemini_chat_payload.json
```

To skip the raw payload backup:

```js
await geminiConversationSnapshot(url, {
  name: "project",
  includeRawPayload: false,
})
```

A custom positive `turnLimit` may also be supplied. The default is 1000 turns.

## Output contract

### `*_gemini_chat_context.md`

Summary-ready text using the same deliberately narrow shape as CWA conversation
snapshots:

```text
## USER

...

---

## ASSISTANT

...
```

Only non-empty textual user/assistant messages are emitted.

### `*_gemini_chat_messages.json`

A normalized experimental envelope:

```json
{
  "schema": "cwa.experimental.gemini.messages.v1",
  "provider": "gemini-web",
  "source_url": "https://gemini.google.com/app/...",
  "conversation_id": "c_...",
  "retrieved_at": "...",
  "rpc": {
    "id": "hNvQHb",
    "decoded_payload_count": 1
  },
  "ordering": "chronological",
  "messages": [
    {
      "role": "user",
      "text": "...",
      "turn_index": 0,
      "request_id": "..."
    },
    {
      "role": "assistant",
      "text": "...",
      "turn_index": 0,
      "request_id": "...",
      "candidate_id": "rc_..."
    }
  ]
}
```

The provider currently returns history newest-first. The probe normalizes it to
chronological order and emits user before assistant within each recovered turn.

### `*_gemini_chat_payload.json`

The decoded body of the `hNvQHb` response. This can contain more product metadata
than the visible text messages, so use the normalized messages/context file for
routine summarization. The raw payload exists to make parser drift diagnosable.

## Current boundaries

This initial proof intentionally does not claim support for:

- public share-link extraction;
- temporary/incognito Gemini chats;
- complete attachment or citation normalization;
- alternate/regenerated response branch selection beyond the first textual
  candidate exposed by the current turn shape;
- Gemini writes, model selection, tools, or generation finality;
- a stable public Gemini API contract.

If the live test succeeds, the next architectural step is not to put Gemini
conditionals inside `ChatGPTProductRuntime`. It is to extract a provider-neutral
conversation snapshot/read contract and implement a Gemini canonical reader
behind that boundary.

## Safety and authority

The probe is intentionally read-only:

```text
conversation observation
!= product mutation
!= permission to write
!= provider-independent canonicality
```

It uses only the already-authenticated Gemini browser session and never exports
cookies or the anti-CSRF token. A failure to parse is treated as protocol drift,
not as an empty conversation.
