# PR15.54 — Post-DeepSeek provider-boundary audit

## Purpose

PR15.53 proved the provider boundary with two materially different providers:

```text
ChatGPT
→ canonical readback required
→ ordinary-chatgpt
→ production browser-owned transport

DeepSeek Web
→ no canonical readback
→ ordinary-deepseek
→ experimental page-owned transport
```

Before adding Gemini, re-audit the shared models for assumptions that were harmless
when ChatGPT was the only real provider but would silently contaminate a third one.

This slice adds no provider feature, browser probe, live harness, or generic runtime.

## Finding 1 — neutral provenance had a ChatGPT fallback

`build_product_execution_provenance(...)` lived in the shared provenance module but
silently used `ordinary-chatgpt` when governance omitted `product_semantics`.

That is no longer valid after PR15.53. A future provider forgetting one field could
produce structurally valid provenance carrying the wrong product semantics.

PR15.54 changes the neutral helper to fail closed:

```text
missing product_semantics
→ RuntimeError
→ no synthesized provider identity
```

The neutral provenance module therefore no longer imports the ChatGPT semantics
constant.

## Compatibility ownership

Existing ChatGPT compatibility is preserved.

`ChatGPTProductRuntime` is explicitly the ChatGPT-specific boundary, so when a
legacy injected ChatGPT transport omits `product_semantics`, that runtime supplies:

```text
ordinary-chatgpt
```

before invoking the neutral provenance builder.

The default does not live in shared provenance anymore.

## Finding 2 — ProductCapabilities legacy constructor default

`ProductCapabilities.from_entries(...)` is already part of the public package
surface and historically defaults to `ordinary-chatgpt`. Removing that default in
this slice would create an unnecessary compatibility break.

Instead PR15.54 proves the important provider invariant:

```text
non-ChatGPT runtime governance = ordinary-deepseek
legacy capability default      = ordinary-chatgpt
→ provider boundary rejects semantics mismatch
```

So the legacy constructor default remains compatibility behavior, not authority for
provider-neutral identity.

Future provider implementations must pass explicit product semantics, as DeepSeek
already does.

## Resulting boundary

After this audit:

```text
provider identity              explicit
product semantics              explicit at provider boundary
neutral provenance semantics   explicit / fail closed
transport identity             explicit
canonical readback             conditional
automatic write retry          forbidden
fallback transport             none
ambiguous write                reconciliation required
incremental observation        not canonical finality
```

No Gemini-specific concept is added here.

## Next

If deterministic CI is green, the boundary has survived:

1. consolidated ChatGPT;
2. real DeepSeek Web;
3. post-second-provider neutrality audit.

Only then should the next bounded slice consider a minimal Gemini Web provider, again
starting with text new-chat + continuation and allowing Gemini evidence to falsify the
boundary rather than pre-generalizing it.
