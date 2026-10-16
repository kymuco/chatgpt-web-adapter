# Independent Qwen installation (Windows)

Run `python -m chatgpt_web_adapter.qwen_native` to prepare the separate extension.
Load `%LOCALAPPDATA%/chatgpt-web-adapter/qwen-native/extension` unpacked in Chrome.
Register its ID with `python -m chatgpt_web_adapter.qwen_native --extension-id ID`.
Reload that extension, then run `python qwen_sdk.py --stream network`.

The host is `com.kymuco.qwen_web_adapter`. Both host and SDK use the independent
`qwen-native/bridge.json` descriptor. Production CWA files and registration are
not changed. A Qwen turn may create a background tab in the same Chrome profile.
This deployment passed offline checks and was also exercised **end-to-end by
the user on Windows before commit `bec72b31` was pushed**. The Python CLI
returned answers across multiple turns with `--stream network`; a later
`--chat UUID` invocation in a fresh process recovered prior conversation
history. Earlier failures were attributed by the user and Codex to
Qwen's **busy/high-demand** state; `/retry` is the implemented explicit
recovery. Do not treat those historical cases as separate unresolved Send or
stream-reading defects. Production ChatGPT/HDE extension installation
remains separate.

## Retry

In interactive browser mode `/retry` regenerates the latest response only when
it shows Qwen high-demand failure. It clicks Regenerate once in the same chat;
it does not append a user message. `QwenClient.retry(conversation=..., on_token=...)`
is the Python equivalent. Interactive errors keep the CLI open. If restarting
the CLI, `/retry` targets the remembered runtime tab, which must still be open.
