# PR8.1 — Browser-Native Turn Provider, Native Messaging Bridge and Persistent ChatGPT Tab Runtime

PR8.1 graduates the successful PR8.0 feasibility probe into a reusable SDK
boundary for ordinary text turns.

## Architecture

```text
ChatGPTWebClient / HDE
        |
        | BrowserNativeTurnProvider (loopback RPC)
        v
Native Messaging host / broker
        |
        | Chrome Native Messaging stdio port
        v
MV3 extension service worker
        |
        | chrome.debugger + CDP Input/Network
        v
persistent background chatgpt.com runtime tab
        |
        | official page-owned protected write
        v
ordinary ChatGPT conversation
        ^
        |
existing SDK get_messages/get_status/attach read path
```

The extension initiates one long-lived `runtime.connectNative()` connection.
Chrome owns the native-host process lifetime, while the host exposes a separate
loopback-only broker for the Python SDK. The extension service worker reconnects
if the native port is lost.

## Security boundary

The browser page owns authentication, device state, Sentinel/Turnstile work, and
the protected conversation POST. The bridge does not export or replay those
credentials.

The Native Messaging response contains only safe turn metadata such as:

- conversation id;
- turn-exchange id when retained by DevTools;
- HTTP status / MIME type;
- runtime tab id and timing diagnostics.

Raw SSE, cookies, authorization headers, Sentinel tokens and Turnstile values are
never returned through the bridge.

The SDK-facing broker binds to `127.0.0.1` on an ephemeral port. A random
per-process token in the local bridge descriptor authenticates requests. The
native host serializes turns so one persistent ChatGPT runtime tab cannot receive
interleaved prompts.

## Persistent runtime tab

The production extension owns one background ChatGPT tab. Its tab id is stored
with `chrome.storage.local` and reused across turns. If the user closes it, the
extension creates a replacement on the next request.

For an existing conversation the runtime tab navigates to `/c/<conversation-id>`.
For a new conversation it navigates to the ChatGPT root. Navigation and turn
submission both use `active: false`; the extension never intentionally activates
or focuses the browser tab.

The page response is not parsed from rendered assistant DOM. The extension waits
only for composer readiness after the protected write. Python then reads the
canonical assistant message through the existing SDK conversation APIs.

## Installation (development / unpacked extension)

Reinstall the editable package so the Native Messaging console-script executable
exists:

```powershell
pip install -e .
```

Register the Native Messaging host:

```powershell
chatgpt-web-adapter browser-native install
```

Print the packaged extension directory:

```powershell
chatgpt-web-adapter browser-native extension-dir
```

Load that directory through `chrome://extensions` -> Developer mode -> Load
unpacked. The manifest carries a stable public key, so the expected extension id
is:

```text
kjfnkhajljnkbhikmfijcchenlfglaie
```

Then verify the bridge:

```powershell
chatgpt-web-adapter browser-native status
```

A healthy runtime reports `available=true` and `extension_connected=true`.

## SDK usage

```python
from chatgpt_web_adapter import BrowserNativeTurnProvider, ChatGPTWebClient

client = ChatGPTWebClient(auth_file="auth_data.json")
client.set_browser_native_turn_provider(BrowserNativeTurnProvider())

response = client.send_browser_native("Reply with exactly: SDK_NATIVE_OK")
print(response.text)

follow_up = client.send_browser_native(
    "Reply with exactly: SDK_NATIVE_CONTINUE_OK",
    conversation=response.conversation,
)
print(follow_up.text)
```

`send_browser_native()` returns a normal `ChatResponse`, but its text comes from
the SDK's canonical conversation readback rather than Native Messaging.

## PR8.1 scope

Supported:

- new ordinary text chat;
- continuation by `ChatConversation`, raw id, or ChatGPT conversation URL;
- persistent background runtime tab;
- safe turn metadata;
- canonical SDK readback;
- one in-flight turn at a time;
- Native Messaging host install/status tooling.

Not yet mapped into browser-native UI semantics:

- explicit model selection;
- explicit reasoning-effort selection;
- `system=` injection;
- `temporary=True`;
- `web_search=True`;
- media uploads;
- approval/tool-control UI.

Those options remain on the existing SDK paths until they receive separate live
characterization. PR8.1 does not silently ignore them because the browser-native
API exposes only the supported arguments.

## Graduation checks

Before making browser-native writes the default transport, live-smoke at least:

1. host install and automatic extension connection;
2. one new-chat turn from Python with no popup interaction;
3. one continuation turn using the returned `ChatConversation`;
4. background/no-focus-steal behavior;
5. account personalization parity;
6. browser close/reopen and native-port recovery;
7. closing the runtime tab and automatic replacement;
8. 20 sequential provider-driven turns with canonical readback;
9. no debugger attachment leaks;
10. Zendriver fallback remains functional when browser-native is not configured.
