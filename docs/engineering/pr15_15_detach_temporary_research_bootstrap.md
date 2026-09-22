# PR15.15 — Detach Temporary research bootstrap from production runtime

Tracking: #107

## Purpose

PR15.12 and PR15.14 established single root owners for native turns and official
page turns, but production startup still entered the old PR8.7 Temporary
characterization chain before reaching the reviewed runtime base.

That meant research history remained part of ordinary service-worker assembly even
though PR15.2 had already removed its `executeNativeTurn` ownership.

PR15.15 removes that bootstrap dependency.

## Before

```text
service_worker_runtime.js
→ service_worker_runtime_legacy.js
→ service_worker_runtime_legacy_impl.js
→ manual Temporary ground truth
→ history probe
→ turn probe
→ semantic/AX/state characterization
→ Temporary mode probe
→ runtime tab reconciliation
→ production runtime
```

## After

```text
service_worker_runtime.js
→ service_worker_runtime_tab_reconciliation.js
→ production runtime
```

The PR8.7 characterization sources remain historical evidence only. They are not
loaded by ordinary production assembly.

## Production dependency retained deliberately

PR8.13.2 startup readiness used the historical
`_pr87TemporaryControlSnapshot` helper as a non-authoritative readiness hint.

PR15.15 copies that exact snapshot semantics into the PR8.13.2 production owner as
`_cwaTemporaryControlSnapshot`. This preserves the readiness signal while removing
the runtime dependency on PR8.7 characterization globals.

The authoritative Temporary write boundary is unchanged:

```text
history_and_training_disabled === true
→ Fetch-paused request proof
→ only then continue product write
```

The UI snapshot remains a readiness hint and grants no write authority.

## Deleted active owners

- `service_worker_runtime_legacy.js`
- `service_worker_runtime_legacy_impl.js`

The second file also contained the active registration for the historical Temporary
characterization RPC family. Those research RPCs are intentionally retired from the
production extension rather than preserved as another runtime facade.

## Preserved invariants

- no automatic product-write retry;
- Browser Authority unchanged;
- Temporary request-body proof remains authoritative;
- canonical finality unchanged;
- ordinary/saved conversation routing unchanged;
- rich-input behavior unchanged;
- diagnostics cannot become write authority by being detached.

## Acceptance

```text
production runtime imports PR8.7 Temporary characterization chain = 0
production reference to _pr87TemporaryControlSnapshot             = 0
single native-turn owner                                         = preserved
single official-page-turn owner                                  = preserved
deleted active legacy bootstrap owners                           = 2
```

This is the first PR15 slice whose primary purpose is deletion of historical
production composition rather than introduction of another owner.
