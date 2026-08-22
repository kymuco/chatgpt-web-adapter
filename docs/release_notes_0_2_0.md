# CWA 0.2.0

Release date: 2026-08-22

CWA 0.2.0 is the first release that treats the ChatGPT product runtime, stable `cwa` CLI, artifact contract, diagnostics, and distribution verification as one release-grade surface.

## Highlights

### Product runtime

- `ChatGPTProductRuntime` is the primary forward-looking application boundary for ordinary text turns.
- The production write path is browser-owned and page-native, with canonical browserless read/status/final readback where available.
- Ambiguous delegated writes do not retry automatically.
- There is no hidden fallback to the historical direct-write path.
- Completion/finality evidence is explicit rather than synthesized from convenience metadata.

### Streaming and model selection

- Revision-safe streaming supports stable incremental observation while preserving canonical final readback.
- Final-only operation is available for callers that do not want speculative/intermediate revisions.
- Public CLI model names use the product-native aliases `INSTANT`, `MEDIUM`, and `HIGH`.
- Compatibility aliases remain `FAST`, `BALANCED`, and `DEEP`.
- `MAX` is intentionally not mapped because no fourth proven product selector is frozen.

### Temporary Chat

- Temporary Chat is graduated for production text-turn use.
- Temporary identity is session-local and is not treated as durable conversation authority.
- Explicit durable-conversation authority cannot be fabricated from a Temporary session id.
- Fresh-session startup readiness is fail-closed before the first product write.

### Stable CLI

The release-grade `cwa` surface includes:

```text
cwa send
cwa status
cwa capabilities
cwa messages
cwa snapshot
cwa export
cwa doctor
```

Stable CLI exit classes are:

```text
0  success
1  observed unavailable state
2  usage/input failure
3  operational failure
4  reconciliation required
```

### Snapshot, export and artifact identity

CWA 0.2 separates:

```text
messages = normalized canonical state now
export   = portable normalized current-branch serialization
snapshot = curated context bundle (+ optional forensic raw payload)
manifest = completion marker with exact byte identity
```

Snapshot/export manifests use schema `1` and record media type, exact byte count and SHA-256 for emitted files. Manifest presence is the bundle-completion marker.

### Diagnostics

`cwa doctor` provides read-only diagnostics across environment, auth, install, bridge, runtime and optional artifact verification.

It does not log in, refresh auth, install the native host, reload the extension, write a product message, repair artifacts, retry an ambiguous write, or enable a fallback transport.

### Packaging and release integrity

- Package version is `0.2.0`.
- Supported Python versions are 3.10 through 3.14.
- CI covers Ubuntu and Windows across Python 3.10-3.14.
- Release candidates build one wheel and one sdist and pass `twine check`.
- The exact wheel is installed into a disposable environment and checked outside the source checkout.
- All packaged Chrome-extension `.json`/`.js` files and the three console entry points are verified from the built wheel.
- Tagged publishing is fail-closed unless Git tag, package version and dated changelog heading agree.
- PyPI publication uses GitHub Release-triggered Trusted Publishing only after the strict release and installed-wheel gates pass.

## Compatibility

`ChatGPTWebClient` remains available as a compatibility surface. Experimental raw/backend helpers and low-level Sentinel/browser-native APIs remain separately classified rather than silently promoted into the stable product-runtime contract.

## Known limitations / intentionally deferred work

CWA 0.2 deliberately freezes the proven text path first.

The stable 0.2 product-runtime contract does **not** yet graduate:

- image upload through the new product-runtime surface;
- general file attachment;
- multimodal continuation in the new product-runtime surface;
- web search, tools or connector orchestration as stable CWA capabilities;
- a production browserless write transport.

Historical compatibility APIs may expose additional experimental/media behavior, but that does not imply those capabilities are part of the frozen 0.2 product-runtime contract.

The current production write transport requires Chrome/Chromium, the packaged extension and the Native Messaging host. A future browserless write transport can be added behind the same product-level contracts after independent characterization.

## Safety / support note

This project is not the official OpenAI API. It operates against an ordinary authenticated ChatGPT web-product session, and product/browser behavior can change independently of this package.

## Release evidence

The release-hardening candidate preceding this finalization passed:

```text
focused PR8.17 tests                 13 PASS
relevant 0.2 regression              50 PASS
README/docs compatibility repair     26 PASS
full repository suite              1286 PASS
wheel + sdist build                  PASS
twine check                          PASS
candidate artifact gate              PASS
local disposable installed wheel     PASS
Ubuntu/Windows Python 3.10-3.14 CI   PASS
cross-platform exact-wheel smoke     PASS
```

The final `v0.2.0` tag must additionally pass the strict tag/version/changelog gate and the publication workflow before the release is considered published.