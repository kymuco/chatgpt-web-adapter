# Qwen background observation, 2026-10-15

The user authorized testing in the existing Chrome profile. Production CWA was
not re-enabled, installed, or modified. Tests used the Browser tool CDP connection
and the current repository helper functions loaded into a separate diagnostic
JavaScript context, without native-host or bridge descriptor writes.

Source baseline: local 6aa8dba9, PR head 1dc1e5ae. Qwen provider and stream source
were identical across these revisions; PR changes quarantine the shared extension.

## Evidence

- Browser tooling initially emulated focus. After explicitly disabling focus
  emulation on the Qwen test target, document.visibilityState was hidden.
- Current _cwaQwenSubmitOnce (Input.insertText and one DOM Send click) sent a
  new-chat prompt. Create-chat and completion requests returned 200; completion
  MIME was text/event-stream. Answer: BACKGROUND_NATIVE_OK.
- A continuation requesting numbers 1 through 60 also ran while hidden.
- Current _cwaQwenObserveStream received CDP events through the diagnostic
  event adapter. Network.streamResourceContent succeeded, 46 answer fragments
  were emitted, and SSE finality was verified. Concatenated answer reached 60.
- The page DOM still ended at 15 while generating=false. This establishes that
  hidden-tab DOM readback can lag behind the finished SSE response.

## Fix

The stream observer now retains and returns the complete verified SSE text.
The provider uses it as the final answer for network mode, instead of returning
potentially truncated DOM text. Existing DOM route and dual-response checks remain.
The offline observer test asserts the assembled answer, not only callback events.

## Limits

This verifies background input and SSE handling via the current helper functions,
not end-to-end Python/native messaging deployment. No reliable TTFT was measured:
diagnostic event polling adds delay. Cold tab creation, recurring age confirmation,
and prolonged background operation still require separate verification. Shared CWA
remains quarantined; no extension deployment was performed for this fix.
