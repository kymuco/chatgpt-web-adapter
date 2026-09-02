# PR12.0 Browser Runtime Architecture

PR12.0 replaces the historical product-wide nested `importScripts(previous_layer)` topology with one stable production entrypoint and four explicit assembly domains.

## Stable entrypoint

`manifest.json` points to `service_worker_runtime.js` (extension version `0.1.14`). The entrypoint contains assembly only and loads, in order:

1. `service_worker_runtime_legacy.js`
2. `service_worker_runtime_write.js`
3. `service_worker_runtime_read.js`
4. `service_worker_runtime_observation.js`

The entrypoint owns no DOM/CDP behavior, Browser Authority, submission, retry, navigation, or canonical-finality interpretation.

## Domains

### Legacy

The legacy domain loads the reviewed PR8/Temporary Chat chain. Historical behavior remains in place, but that chain no longer decides which later write/read/observation layers exist.

### Write

The write domain assembles rich-input staging/authority, the reviewed schema chain, bounded UI compatibility discovery, and ordinary-text protected commit-point hardening.

Only the already-reviewed write layers own submit behavior. PR12.0 adds no new write fallback or retry path.

### Read

The read domain assembles product source/citation observation and authenticated browser-context canonical reads. It does not gain write or retry authority.

### Observation

The observation domain assembles connector characterization followed by UI liveness. Connector support remains the terminal `executeNativeTurn` characterization wrapper; liveness remains a Native Messaging observation wrapper and grants no write, retry, or canonical-finality authority.

## Quarantined historical internals

PR12.0 intentionally does not rewrite every older PR8/PR9 schema/diagnostic file. The dense historical chains remain reviewed compatibility payload inside their owning domain. The architectural change is that cross-domain ownership is no longer hidden in those files.

The following old cross-domain links are removed:

- Temporary route-reopen no longer imports PR9 rich input or PR10 connector support;
- the PR9 rich-schema loader no longer imports UI compatibility, text-submit hardening, source/citation observation, or canonical read;
- connector support no longer imports UI liveness.

## Rule for future browser-runtime work

New product capabilities must be attached through the stable runtime/domain assembly or a later explicit module registry. Do not extend the product by adding another `service_worker_*_repair.js` that imports the previous product-wide layer.

A historical compatibility file may continue to import another file inside the same quarantined historical domain until it is migrated, but it must not regain cross-domain assembly ownership.

## Preserved invariants

PR12.0 is an assembly refactor. It preserves the established contracts from PR11:

- browser-owned write and Browser Authority fencing;
- no automatic replay after ambiguous submission;
- first-class submission acceptance versus canonical finality;
- browser-context canonical read with Python semantic/finality authority;
- UI liveness as observation only;
- bounded UI-drift compatibility discovery;
- Temporary Chat and rich-input specialized write paths.
