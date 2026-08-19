# PR8.7 T13 — Temporary Chat capability graduation review

_Status: CLOSED / PASS — reviewed, not graduated to AVAILABLE_

_Date: 2026-08-16_

_Review base: PR8.7 live characterization plus production governance T8–T12_

## Decision

The explicit T13 capability review does **not** graduate `temporary_chat` to `AVAILABLE`.

The reviewed production classification is:

```text
temporary_chat = UNIMPLEMENTED
production conversation_mode="temporary" = DISABLED
```

This is a deliberate reclassification from the earlier conservative `UNKNOWN`, not a regression in evidence.

`UNKNOWN` was appropriate while Temporary semantics and lifecycle behavior were still being characterized. PR8.7 now has strong evidence that the ChatGPT product exposes a real live multi-turn Temporary conversation mode and has explicit production governance for no-fallback, provenance, mode isolation, and lifecycle/recreation boundaries.

However, `AVAILABLE` means the declared runtime itself implements and evidence-backs the capability. The current production `ProductWriteTransport` remains ordinary-mode-only, and `ChatGPTProductRuntime` still rejects `conversation_mode="temporary"` before transport dispatch. By the existing `CapabilityState` taxonomy, the accurate state is therefore `UNIMPLEMENTED`: the product/transport concept exists, but this runtime does not currently implement the production route.

## Evidence accepted by T13

The review accepts the following PR8.7 evidence as established:

```text
live true Temporary first turn                         PROVEN
live true Temporary sequential multi-turn              PROVEN
same Temporary product conversation identity           PROVEN
live visible turn growth 0 -> 2 -> 4                   PROVEN
ordinary history while live                            STABLE_ABSENT
ordinary canonical GET while live                      404 / NOT_FOUND
ordinary canonical GET after source close              404 / NOT_FOUND
post-close direct product route recovery               STABLE_RECOVERED
all four completed turns recovered after close         PROVEN
post-close controlled continuation                     HTTP 404
no normal durable fallback                             CLOSED / PASS
requested/observed mode provenance                     CLOSED / PASS
TEMP -> NORMAL isolation                               CLOSED / PASS
NORMAL -> TEMP isolation                               CLOSED / PASS
cold/warm/runtime-tab recreation governance            CLOSED / PASS
```

These observations are sufficient to define the target semantics and the safety boundary. They are not sufficient to claim that the current production runtime implements that target.

## Why AVAILABLE is denied

The capability is not graduated because the current production runtime is missing the execution path that would have to satisfy the PR8.7 contract.

The blocking implementation/evidence gaps are:

```text
1. no mode-aware Temporary ProductWriteTransport route
2. no production first-write path that proves observed_mode=TEMPORARY before mutation
3. no production live Temporary continuation path bound to the same proven lifecycle
4. no production integration that emits PRODUCT_MODE_OBSERVATION for successful TEMP execution
5. no production integration that emits a proven LIVE ProductTemporaryLifecycleProvenance
6. no production Temporary finality path independent of ordinary canonical conversation GET
7. no production disposal/loss path that transitions a live Temporary lifecycle to ENDED
8. no live production validation of the eventual integrated route across fresh sessions
```

Manual and dedicated research probes establish product semantics. They do not substitute for evidence that `ChatGPTProductRuntime.send(..., conversation_mode="temporary")` itself obeys those semantics.

## Why UNIMPLEMENTED is more accurate than UNKNOWN

The project capability taxonomy defines:

```text
AVAILABLE     implemented and evidence-backed on the declared runtime
UNSUPPORTED   relevant contract is known not to provide the capability
UNKNOWN       not characterized strongly enough
UNIMPLEMENTED product/transport may expose the concept, but this runtime does not implement it
```

After T2–T12, Temporary is no longer weakly characterized. It is also not known to be unsupported by the ChatGPT product; the live probes demonstrate the opposite.

Therefore:

```text
UNKNOWN -> UNIMPLEMENTED
```

is the evidence-consistent T13 decision.

## Production invariants that remain in force

T13 does not relax any prior safety gate:

```text
conversation_mode="temporary"
    -> fail closed before ProductWriteTransport
    -> zero product write
    -> fallback = none

ordinary runtime tab
    != Temporary mode proof

Temporary product conversation ID
    != live Temporary write authority

runtime-tab recreation
    != Temporary lifecycle recreation

post-close /c/<id> recovery
    != continuation authority
```

Changing only the capability state in a future patch must never be sufficient to enable Temporary writes. The T8 runtime gate remains an independent defense until a dedicated mode-aware route is implemented and reviewed.

## Required future graduation evidence

A future review may consider `UNIMPLEMENTED -> AVAILABLE` only after all of the following are implemented and demonstrated on the actual production runtime path:

```text
A. explicit mode-aware Temporary write routing
B. first write with requested=TEMPORARY and observed=TEMPORARY proven before mutation
C. ProductTemporaryLifecycleProvenance with proven LIVE write authority
D. at least two sequential production Temporary turns in one live lifecycle
E. stable Temporary product identity across those turns
F. page-owned Temporary finality without inventing ordinary canonical-read proof
G. explicit lifecycle termination/disposal that revokes write authority
H. post-termination continuation denied without durable fallback
I. TEMP -> NORMAL and NORMAL -> TEMP isolation preserved
J. cold/warm/runtime-tab recreation invariants preserved
K. independent fresh-session replication of the integrated production path
```

Only then may the browser-owned capability declaration be changed to:

```text
temporary_chat = AVAILABLE
```

## T13 closure

T13 is closed because the review has produced an explicit, evidence-backed classification and has prevented premature graduation.

```text
T13 review status             = CLOSED / PASS
AVAILABLE graduation          = DENIED
reviewed capability state     = UNIMPLEMENTED
production Temporary send     = DISABLED
next transition               = UNIMPLEMENTED -> AVAILABLE only after implementation + live production evidence
```

PR8.7 has therefore completed the Temporary semantic characterization and production-governance review. What remains is not more semantic guessing; it is implementation and validation of the dedicated production Temporary route under the contract established here.
