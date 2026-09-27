# Browser-owned execution

_Last updated: 2026-09-26_

Browser-owned execution is the reference/default mutation strategy for ordinary
consumer AI web products in CWA.

It is not considered an architectural failure merely because it requires a browser.

## Why a real browser is useful

A signed-in browser already owns:

```text
session cookies
frontend JavaScript
normal product navigation
page-owned upload behavior
page-owned submit behavior
product challenge/protection state
```

Reproducing those semantics outside the browser often means taking ownership of
private web protocols that change more frequently than the product surface itself.

CWA therefore prefers to keep the browser responsible for browser/product concerns.

## CWA's bounded responsibility

The desired shape is:

```text
local caller
→ resolve governed product surface
→ perform one bounded write
→ observe outcome
→ reconcile ambiguity if needed
```

The browser is an execution resource. It does not become downstream policy authority.

A runtime tab or page route is not, by itself:

- caller approval;
- canonical finality;
- retry permission;
- filesystem/Git authority;
- agent continuation authority.

## Background runtime tabs

A reusable background tab is a practical implementation resource.

It lets the product retain its ordinary authenticated environment while avoiding a new
interactive browser setup for every turn.

The implementation does not intentionally foreground an existing runtime tab merely to
send a turn, although browser behavior on a cold/new tab can still be visible.

CWA treats tab ids and CDP targets as private implementation details.

## Browser-owned does not mean DOM-as-truth

The browser can own mutation while finality comes from a different plane.

For ChatGPT:

```text
browser-owned write
→ canonical conversation readback
→ durable completion authority
```

For current DeepSeek/Gemini proofs:

```text
browser-owned page write
→ stable page observation
→ noncanonical completion evidence
```

The architecture keeps those claims distinct.

## Browserless execution

Browserless web-product access is technically possible and may be useful.

CWA already contains the experimental ChatGPT transport:

```text
browserless-request
```

But avoiding Chrome is not sufficient evidence for promotion.

Browserless web-product reproduction can require ownership of:

- undocumented request schemas;
- session/header details;
- frontend-generated correlation values;
- product protection/challenge flows;
- revision-sensitive request behavior.

CWA will not add challenge-bypass machinery simply to make a direct-request path look
reliable.

The browserless path should remain evidence-driven and fail closed.

## Official APIs

Official provider APIs are a separate integration category.

```text
official API semantics
!= ordinary consumer web-product semantics
```

An application that only needs model inference may be better served by an official
API.

CWA is useful when the ordinary product itself is the integration target.

## Retry boundary

Browser-owned execution does not authorize automatic replay.

Core rule:

```text
write known not to have happened
→ ordinary failure may be retryable by explicit caller policy

write may have happened
→ reconciliation required
→ no automatic retry
```

For page-owned DeepSeek/Gemini submission, ambiguity begins once the click-capable
`Runtime.evaluate` may have executed the page's send control.

Known navigation detach can transition to observation-only reattachment; it never
authorizes a second click.

## Security boundary

The browser extension and Native Messaging bridge are high-trust local components.

They must not export:

- session cookies;
- authorization headers;
- challenge credentials;
- arbitrary raw page state;
- private connector data;
- capability-bearing signed locators.

See [../SECURITY.md](../SECURITY.md).

## Decision rule

Prefer browser-owned execution when it materially reduces private-protocol ownership
and preserves stronger product semantics.

Promote browserless execution only when a concrete consumer benefit and durable
evidence justify the extra protocol ownership.
