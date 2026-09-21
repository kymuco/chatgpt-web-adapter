# PR15.13 — Observability page-turn composition

## Goal

Remove import-order ownership from the response-observation
`executeOfficialPageTurn` stack without crossing into Temporary or rich-input
write authority.

## Historical order

Before this change, the observability/response page-turn chain was assembled by
seven global assignments:

```text
early-completion repair
→ early completion
→ post-answer tail timing
→ safe browser stream
→ Instant observation
→ phase timing
→ stale-UI recovery implementation
```

The recovery layer is the terminal page-turn implementation rather than a wrapper.

## After

The six observability wrappers expose `(args, next)` functions. Recovery exposes
its terminal implementation as a named function.

`service_worker_observability_page_turn_lifecycle.js` is the only global
`executeOfficialPageTurn` owner for this cluster. It is loaded immediately after
early-completion repair and before normalized activity, preserving the historical
outer boundary. Later Temporary and rich-input page-turn layers therefore still
wrap the same complete observability stack.

## Preserved boundaries

This refactor does not change:

- stale-UI reload behavior;
- phase timing intervals;
- Instant observation;
- streaming request/response observation;
- post-answer tail timing;
- early-product completion acceptance or repair;
- Temporary session identity;
- rich-input staging, protected submit, or committed identity;
- Browser Authority or canonical finality.
