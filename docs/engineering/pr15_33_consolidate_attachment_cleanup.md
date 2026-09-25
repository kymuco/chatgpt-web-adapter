# PR15.33 — Consolidate attachment cleanup/fence ownership

## Purpose

Continue #107 by removing the remaining source-order ownership chain around the
three attachment cleanup/fence capabilities:

```text
_pr92PersistDirtyAttachmentFence(...)
_pr92TryClearDirtyAttachmentFence(...)
_pr92ClearOfficialPageAttachments(...)
```

The shipping history is not one uniform chain:

```text
fence persistence:       base → schema7
fence clear:             base → deadline repair → schema7
destructive stale cleanup:
                          base → deadline repair → schema7 → schema8
```

Production previously depended on the last assignment loaded for each shared name.

## New ownership

Historical generations remain explicit named helpers:

```text
base:
  _pr92BasePersistDirtyAttachmentFence(...)
  _pr92BaseTryClearDirtyAttachmentFence(...)
  _pr92BaseClearOfficialPageAttachments(...)

deadline:
  _pr92DeadlineTryClearDirtyAttachmentFence(...)
  _pr92DeadlineClearOfficialPageAttachments(...)

schema7:
  _pr92Schema7PersistDirtyAttachmentFence(...)
  _pr92Schema7TryClearDirtyAttachmentFence(...)
  _pr92Schema7ClearFencedRuntimeTab(...)

schema8:
  _pr92Schema8ClearFencedRuntimeTab(...)
```

The sole public production owner is:

```text
service_worker_attachment_cleanup.js
```

It explicitly graduates the final effective generations:

```text
_pr92PersistDirtyAttachmentFence(...)
→ _pr92Schema7PersistDirtyAttachmentFence(...)

_pr92TryClearDirtyAttachmentFence(...)
→ _pr92Schema7TryClearDirtyAttachmentFence(...)

_pr92ClearOfficialPageAttachments(...)
→ _pr92Schema8ClearFencedRuntimeTab(...)
```

## Why direct graduation is correct

Schema7's three historical `Prior*` captures were not part of its implementation;
they were source-order residue. Its persistence, fence-clear, and destructive cleanup
implementations replace the earlier generations wholesale.

Schema8 then replaces only destructive stale-tab cleanup. All runtime consumers
resolve the public capability names at call time after write-domain assembly completes.

The explicit owner therefore reproduces the effective production generation for each
capability without retaining load order as the ownership mechanism.

## Preserved authority semantics

PR15.33 does not change attachment cleanup authority.

The final schema7 fence behavior still preserves:

- durable local fence persistence before file selection;
- browser-session identity for destructive cleanup authority;
- local + session identity agreement;
- fail-closed behavior when session identity is missing after browser restart;
- no same-turn fence retirement after attachment staging;
- bounded fence clearing under the active turn deadline.

The final schema8 destructive cleanup still preserves:

- no destructive close during a staged rich turn;
- ChatGPT runtime URL checks;
- current runtime-tab identity checks;
- local/session fence identity checks;
- change listeners that invalidate ownership before close dispatch;
- final authority re-read immediately before destructive close;
- no `await` between the final guard and `chrome.tabs.remove(...)`;
- explicit tab-absence proof before cleanup succeeds.

No write, submit, retry, navigation, attachment-byte transport, evidence, or finality
authority is added.

## Assembly

```text
service_worker_rich_input_schema7_repair_pr9_2.js
→ service_worker_attachment_evidence.js
→ service_worker_attachment_cleanup.js
→ service_worker_attachment_staging.js
→ service_worker_rich_input_lifecycle.js
```

All historical helpers exist before the public owner is installed.

## Static target

```text
_pr92PersistDirtyAttachmentFence public definitions       = 1
_pr92PersistDirtyAttachmentFence runtime assignments       = 0
_pr92TryClearDirtyAttachmentFence public definitions       = 1
_pr92TryClearDirtyAttachmentFence runtime assignments       = 0
_pr92ClearOfficialPageAttachments public definitions        = 1
_pr92ClearOfficialPageAttachments runtime assignments        = 0
Prior* cleanup/fence aliases                                 = 0
```

## Regression strategy

PR15.33 verifies:

- one public owner for all three cleanup/fence capabilities;
- zero historical runtime reassignments;
- base/deadline/schema7/schema8 generations remain explicit helpers;
- direct graduation to schema7/schema7/schema8 respectively;
- write-domain assembly installs the owner after schemas and before staging;
- each public owner delegates exactly once without argument drift;
- existing attachment consumers resolve the public owner dynamically.

Tracking: #107
