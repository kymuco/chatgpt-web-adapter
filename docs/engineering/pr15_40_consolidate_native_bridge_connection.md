# PR15.40 — Consolidate native-bridge connection ownership

## Purpose

Continue #107 by removing source-order replacement from:

```text
connectNativeBridge()
```

and record the exact-main closure audit result before declaring the PR15
ownership pass complete.

## Historical composition

The base worker creates the native connection and invokes it immediately during
bootstrap. PR11.0 later captures that public binding and replaces it with a
product-state wrapper:

```text
base native connection
→ PR11 product-state wrapper
```

The product wrapper adds no native messaging authority. It only attaches
disconnect-driven UI state refresh and updates the extension action state.

## Explicit stages

PR15.40 names the base and product stages directly:

```text
_cwaBaseConnectNativeBridge()
_cwaConnectNativeBridgeWithProductState()
```

The sole public production owner is:

```text
service_worker_native_bridge_connection.js
```

with explicit future-call composition:

```text
connectNativeBridge()
→ _cwaConnectNativeBridgeWithProductState()
→ _cwaBaseConnectNativeBridge()
```

## Preserved bootstrap semantics

The first extension bootstrap connection intentionally happens before the PR11
product surface is loaded.

Therefore the base worker now performs only the initial call directly:

```text
_cwaBaseConnectNativeBridge();
```

The existing PR11 product layer then attaches product-state listeners to an
already-connected `nativePort` when present.

Future reconnect, install, and startup callbacks continue resolving the public
`connectNativeBridge` name dynamically. By then the product helper and public
owner have been installed, so those calls traverse the explicit product-state
composition.

This preserves the historical distinction:

```text
initial bootstrap = base connection first, product state attaches afterward
future connection = public owner → product wrapper → base
```

## Static target

```text
connectNativeBridge public definitions = 1
connectNativeBridge runtime assignments = 0
_cwaProductPriorConnectNativeBridge aliases = 0
```

## Authority

PR15.40 changes connection ownership only.

It does not add:

- native message routing authority;
- ChatGPT product-write authority;
- retry authority beyond the existing reconnect scheduler;
- navigation authority;
- canonical finality.

## Closure audit result

An exact-main audit from
`a72768e6df153ee97928ee5096c663ec715da717` confirmed that
`connectNativeBridge` is not the final source-order mutation in shipping code.

Confirmed remaining clusters include:

```text
request inspection:
  _pr92Schema29InspectRequestPostData
    schema29 base → request-text-shape compat → browser-indent compat

runtime lifecycle:
  executeNativeTurn
  executeOfficialPageTurn
  storedRuntimeTabId

recovery / deadline:
  waitForTabComplete
  _pr811ReloadRuntimeTabAndWait
  _pr811MaybeRecoverStaleRuntimeUi

rich-input schema hooks:
  _pr92ClosureReadPageOwnedAttachmentEvidence
  waitForSendButtonPoint
  _pr92Schema10RequireOfficialCleanComposerBeforeStaging
  _pr92Schema12ObservePostStageAttachmentEvidence
  _pr92ReadDirtyAttachmentFence
  _pr92Schema17OptionalPostWrite

temporary-state semantics:
  _pr87TemporaryControlSnapshotExpression
```

This is a confirmed working inventory, not yet a proof of exhaustiveness.
The final PR15 ownership closure will require a static gate over the shipping
worker surface after these clusters are consolidated.

## Next direction

Prefer bounded slices by semantic domain rather than one large cleanup PR:

1. request-inspection ownership;
2. runtime lifecycle / tab-state ownership;
3. recovery/deadline ownership;
4. rich-input schema-hook ownership;
5. temporary-state snapshot ownership;
6. final static no-reassignment closure gate.

Tracking: #107
