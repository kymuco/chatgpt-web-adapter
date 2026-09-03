# PR12.2 — First-Class Product Runtime Surface

PR12.2 removes import-order-dependent installation of the split submission lifecycle and browser UI liveness methods from `ChatGPTProductRuntime`.

The runtime class itself owns the public methods `submit`, `await_final`, `submission_lifecycle_snapshot`, and `observe_ui_liveness`. Helper modules implement bounded transport-specific mechanics, but they do not mutate the runtime class or replace `governance()` at import time.

The historical `product_submission_runtime_gate` and `product_ui_liveness_runtime_gate` modules remain as compatibility validators only. Calling their installer functions verifies that the first-class methods exist and preserves method identity.

Behavioral contracts are unchanged:

- submission acceptance is not canonical finality;
- `await_final` remains the canonical-resolution stage;
- unsupported split submission fails closed before write;
- UI liveness remains non-authoritative observation;
- liveness never grants write authority, retry authority, or canonical finality;
- Browser Authority and transport selection semantics are unchanged.

PR12.2 intentionally leaves the older `send_text_observed` package-import wrapper for the later import-time mutation cleanup. The scope here is only the methods that previously did not exist in the runtime class body at all.
