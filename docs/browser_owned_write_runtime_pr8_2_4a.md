# PR8.2.4a — Runtime-Tab Provisioning Observability

PR8.2.4a repairs an ambiguity discovered by the PR8.2.4 live write: the Python
runtime does not launch a Chrome process, but the connected extension may create
its dedicated ChatGPT runtime tab on demand. This PR makes process ownership,
tab provisioning, and foreground activation separate observable facts.

## Scope

The transport remains the proven PR8.1/PR8.1.1 browser-native path. This PR does
not change composer interaction, the submit ladder, stale-UI recovery, protected
product-write execution, auth/session renewal, or canonical readback.

A new extension wrapper, `service_worker_observability.js`, imports the existing
recovery worker and surrounds one `executeNativeTurn` call with bounded tab
observation only.

## Safe write metadata

The extension may return:

- `runtimeTabPreexisting`
- `runtimeTabCreatedForTurn`
- `tabActiveAfter`
- `tabActivatedDuringTurn`
- `foregroundActivationObserved`

The existing `tabWasActive` field remains the observation at write start.
Python preserves missing PR8.2.4a metadata as `None` rather than converting it
to `False`, so an older extension cannot create false negative evidence.

`foregroundActivationObserved == false` means only that the runtime tab was not
active at write start, was not observed in `chrome.tabs.onActivated` during the
turn, and was not active after the write. It is not a claim about every possible
OS-level presentation event.

## Ownership semantics

Authoritative governance fields are:

- `browser_process_launch_owned_by_runtime = false`
- `runtime_tab_creation_owned_by_extension = true`
- `runtime_tab_creation_on_demand = true`
- `runtime_tab_foreground_activation_requested = false`

The older `browser_launch_owned_by_runtime = false` field is retained as a
compatibility alias but is no longer sufficient by itself to describe runtime
ownership.

## Production observation API

`BrowserOwnedProductWriteRuntime.send_text_observed()` remains a normal
failure-safe PR8.2.4 send and additionally captures the safe
`browser_native_write_completed` event into:

- `BrowserOwnedWriteExecution.response`
- `BrowserOwnedWriteExecution.observation`

The existing `send_text()` contract is unchanged.

## Live gates

With a connected extension and no pre-existing dedicated runtime tab, the first
write should report:

```text
runtime_tab_preexisting        false
runtime_tab_created_for_turn   true
foreground_activation_observed false
```

Without closing that tab, a second write should report:

```text
runtime_tab_preexisting        true
runtime_tab_created_for_turn   false
foreground_activation_observed false
```

These gates establish on-demand inactive provisioning followed by reuse without
observed foreground activation.

## Governance boundary

PR8.2.4a does not add direct protected writes, cookie or credential extraction,
Sentinel/Turnstile/proof reconstruction, browser-process launching, or native UI
automation outside the already proven page-owned write path.
