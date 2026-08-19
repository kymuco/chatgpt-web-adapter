# PR8.2.4a.3 — Live Runtime-Tab State Reconciliation

PR8.2.4a.3 repairs stale runtime-tab identity in the browser-native control plane.

The live PR8.2.4a.2 validation established two facts at once:

1. canonical status/readback and same-conversation product write are now healthy;
2. the Native Messaging health path can temporarily report a stale stored tab id as
   `runtime_tab_preexisting=true` even though the extension rejects that id immediately
   before the write and creates a replacement inactive ChatGPT tab.

Observed sequence:

```text
health.runtime_tab_id = 1949458801
health.runtime_tab_preexisting = true

write.runtime_tab_id = 1949459425
write.runtime_tab_preexisting = false
write.runtime_tab_created_for_turn = true
```

A second turn then reused `1949459425` successfully, proving that ordinary same-tab
reuse itself works. The defect is stale persistent/broker identity, not the transport
reuse algorithm.

## Root cause

The Native Messaging broker caches the last `runtimeTabId` published by the extension.
The base extension previously read `browserNativeRuntimeTabId` from `chrome.storage`
and could publish that integer during connect/reconnect before proving that the Chrome
tab still existed and still belonged to `https://chatgpt.com`.

`ensureRuntimeTab()` was stricter: immediately before a write it performed
`chrome.tabs.get(storedId)` plus the ChatGPT-origin check. Therefore health and the
actual write could disagree.

## Repair

The manifest now routes through `service_worker_runtime_tab_reconciliation.js`, which
imports the already-proven observability/recovery/transport chain and changes only the
runtime-tab registry read boundary.

Every future `storedRuntimeTabId()` read now means:

```text
read integer from storage
→ chrome.tabs.get(id)
→ require chatgpt.com origin
→ valid: return id
→ invalid/missing: clear storage + publish runtime_state(null)
```

This automatically strengthens existing consumers, including `ensureRuntimeTab()`,
the inherited tab-removal listener, and future Native Messaging reconnect `hello`
messages.

Because the base worker may already have connected while the wrapper chain was loading,
PR8.2.4a.3 also performs one immediate post-load reconciliation and republishes the
validated state. Thus a stale initial hello is corrected without waiting for a turn.

## Lifecycle reconciliation

The wrapper additionally handles two state transitions that are not equivalent to a
normal tab close:

- `chrome.tabs.onUpdated`: if the stored runtime tab navigates away from ChatGPT, clear
  the stored id and publish `runtime_state(null)`.
- `chrome.tabs.onReplaced`: if Chrome replaces the stored tab with another valid
  ChatGPT tab, adopt the replacement id through the existing `storeRuntimeTabId()`;
  otherwise clear the removed id.

All clear/adopt operations are compare-before-write guarded so a late lifecycle event
cannot erase a newer runtime tab id.

## Governance

After this PR, `runtime_tab_preexisting=true` remains a point-in-time snapshot rather
than a timeless guarantee, but it is no longer intended to mean merely “an integer was
found in extension storage.” The extension reconciles storage against live Chrome tab
state on load/reconnect, on relevant tab lifecycle events, and before every existing
stored-id reuse path.

This PR does **not** claim that the execution tab is hidden. Browser-owned writes still
use one real inactive ChatGPT tab in the Chrome tab strip. The repair only prevents
stale identity from causing false-preexisting diagnostics and avoidable replacement-tab
creation.

## Safety boundary

PR8.2.4a.3 does not modify composer interaction, CDP Input, the submit ladder, protected
product-write execution, canonical readback, auth/session renewal, cookies, Sentinel,
Turnstile, proof handling, or automatic retry policy.

It adds no direct private product write and no browser-protection bypass behavior.

## Acceptance gates

A stale stored id after reconnect/startup should reconcile to:

```text
runtime_tab_id = null
runtime_tab_preexisting = false
```

before an explicit write begins.

A valid stored ChatGPT tab should remain stable across health and write:

```text
health.runtime_tab_id == write.runtime_tab_id
write.runtime_tab_preexisting = true
write.runtime_tab_created_for_turn = false
foreground_activation_observed = false
```

After a stored runtime tab navigates away from ChatGPT, health should no longer publish
that id. After a valid Chrome tab replacement, health should publish the replacement id.
