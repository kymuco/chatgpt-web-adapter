# PR14.8 — Retained Conversation Tabs

## Purpose

Ordinary saved conversations previously shared one browser-owned runtime tab.

That was sufficient for isolated requests, but a Codexia/worker loop repeatedly moved
the same product surface between:

```text
/c/<codexia>
-> /c/<worker>
-> /c/<codexia>
-> /c/<worker>
```

The semantic loop was already correct, but this navigation churn increased product
surface work and made long-lived multi-conversation use unnecessarily fragile.

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

## Live acceptance target

The first consumer-driven live validation should use two existing saved
conversations, ideally Codexia plus one persistent worker:

```text
turn 1 -> Codexia conversation
turn 2 -> Worker conversation
turn 3 -> Codexia conversation
turn 4 -> Worker conversation
```

Acceptance requires:

```text
Codexia tab id remains stable across turns 1 and 3
Worker tab id remains stable across turns 2 and 4
Codexia tab id != Worker tab id
both tabs remain inactive/background unless already user-activated
conversation identities remain exact
no duplicate product turn
no automatic retry
Temporary Chat behavior unchanged
```

This is deliberately a routing milestone. Multi-chat selection, naming, temporary
Codexia sessions and general tab-management UI remain consumer-level follow-up work.
