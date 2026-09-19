# PR14.8 — Retained Conversation Tabs

## Purpose

Ordinary saved conversations previously shared one browser-owned runtime tab.

That was sufficient for isolated requests, but any alternating use of two saved
conversations repeatedly moved the same product surface between routes:

```text
/c/<conversation-a>
-> /c/<conversation-b>
-> /c/<conversation-a>
-> /c/<conversation-b>
```

This navigation churn increased product-surface work and made long-lived
multi-conversation use unnecessarily fragile. PR14.8 treats that as a CWA transport
property rather than a consumer-specific workflow concern.

PR14.8 changes only browser routing for normal **saved** conversations:

```text
conversation_id A -> retained background tab A
conversation_id B -> retained background tab B
```

It does not create a new semantic scheduler, parallel write executor, conversation
registry, retry policy, or Temporary Chat recovery mechanism.

## Scope

The runtime stores a bounded local mapping:

```text
browserNativeConversationTabsV1
[
  { conversationId, tabId },
  ...
]
```

The initial pool bound is 16 retained saved conversations. Reaching the bound fails
closed rather than evicting an existing conversation tab implicitly.

For a saved conversation turn:

1. reuse its exact retained tab when the tab still exists and remains on the exact
   `/c/<conversation_id>` route;
2. otherwise remove the stale binding;
3. if the historical single runtime tab already points at the exact requested
   conversation, adopt that tab into the pool rather than opening a duplicate;
4. otherwise create one inactive ChatGPT tab for that exact conversation;
5. verify the loaded route before persisting the binding.

No retained tab is navigated to another conversation.

## Fresh normal chats

A fresh normal chat still uses the existing legacy runtime-tab path.

If the historical runtime-tab pointer happens to reference a tab that has since
become conversation-bound, PR14.8 clears only that pointer before delegating the
fresh-chat acquisition. It does not close or navigate the retained conversation tab.

This preserves:

```text
saved conversation tab != fresh-chat scratch tab
```

A newly-created normal conversation can later be adopted into the retained pool on
its first continuation, once a stable conversation id exists.

## Temporary Chat boundary

Temporary Chat keeps its existing process-local lifecycle and dedicated tab
authority.

PR14.8 explicitly delegates to the pre-existing Temporary path whenever the
Temporary turn context is live. It does not read or write Temporary lifecycle
tokens, does not synthesize Temporary conversation recovery, and does not infer
Temporary mode from a URL.

Therefore:

```text
saved-conversation tab pool
!= Temporary Chat lifecycle
```

## Rich-input ordering

The retained-tab layer is assembled **before** the rich-input wrappers.

That ordering is intentional. Rich-input deadline, staging, cleanup and recovery
wrappers remain outside the new routing layer and therefore keep their existing
semantics while acquiring the retained saved-conversation tab underneath.

## Stale binding repair

Bindings are local routing hints, never conversation authority.

They are removed when:

- the Chrome tab disappears;
- the tab navigates away from its bound conversation;
- exact route validation fails on acquisition.

Chrome tab replacement is accepted only when the replacement tab is still on the
same exact conversation route. Otherwise the binding is dropped.

A missing or stale binding never authorizes product replay. The next turn simply
requires a fresh tab acquisition before the normal protected write path can run.

## Authority boundaries

PR14.8 does not add or change:

- product submit authority;
- canonical finality;
- conversation identity inference;
- ambiguous-write retry authority;
- generated-artifact handoff;
- filesystem authority;
- Temporary Chat authority;
- parallel product writes.

The new layer does not type, click, call the conversation endpoint, perform
canonical reads, or retry a product write. It only chooses which background
ChatGPT tab the already-governed write runtime should use.

## Product-surface behavior

Conversation tabs are created with:

```text
active = false
```

The milestone does not intentionally foreground them.

The existing extension popup/runtime-state surface still describes the historical
single runtime-tab slot; PR14.8 does not widen that UI contract into a conversation
tab manager. A user-facing conversation selector belongs to a later consumer
milestone.

## Deterministic acceptance

Regression coverage freezes these invariants:

- PR14.8 is assembled before rich-input wrappers;
- saved conversations have a bounded conversation-id/tab-id pool;
- the exact route is validated before reuse or binding;
- a fresh normal chat never repurposes a retained saved-conversation tab;
- Temporary Chat delegates to its prior lifecycle;
- removed, retargeted and replaced tabs reconcile bindings;
- no product submit/read/retry primitive is introduced by this layer.

## CWA-owned live acceptance

PR14.8 is validated by CWA itself. No consumer runtime is part of the proof surface.

The dedicated gate performs seven bounded product writes:

```text
A seed
A continuation -> bind retained tab A
B seed
B continuation -> bind retained tab B
A revisit       -> exact tab A
B revisit       -> exact tab B
Temporary turn  -> dedicated Temporary tab -> explicit close
```

Acceptance requires:

```text
deployment identity is healthy and bound to the installed CWA revision
conversation A tab id remains exact on revisit
conversation B tab id remains exact on revisit
conversation A tab id != conversation B tab id
Temporary tab id differs from both saved-conversation tabs
Temporary mode/prewrite/page-owned finality are proven
explicit Temporary close enters after the proven turn
ENDED is emitted only by the deployed extension after owned-tab absence proof
no duplicate product turn
no automatic retry
```

Run the exact CWA-owned gate:

```powershell
python -m chatgpt_web_adapter.retained_conversation_tabs_live_gate \`
  --auth-file auth_data.json \`
  --acknowledge-live-writes
```

The gate intentionally relies only on CWA's public runtime plus its deployment
identity evidence. It does not inspect or depend on Codexia, HDE, or another
consumer. Multi-chat naming/selection and consumer UI remain outside this routing
milestone.
