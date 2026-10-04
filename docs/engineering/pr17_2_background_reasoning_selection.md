# PR17.2 — Background Reasoning Selection without Foreground Churn

Status: SHIPPING CAPABILITY PROVEN; conversation-scope proof remains separate.

## Outcome

PR17.2 started by testing whether ChatGPT exposed stable direct discrete
`Instant / Medium / High` option controls that could replace the inherited
reasoning-effort slider path.

That hypothesis was not promoted to production. The live product surface was
more reliable through the existing discrete `0..2` reasoning slider.

The shipping result instead removes the user-visible foreground requirement:

```text
requested profile
  -> prove current composer-local mode
  -> enable CDP focus emulation while the runtime tab remains inactive
  -> open the product reasoning picker
  -> resolve the proven 0..2 reasoning slider
  -> focus that resolved slider through CDP DOM.focus
  -> Home proves INSTANT / 0
  -> bounded ArrowRight steps prove MEDIUM / 1 or HIGH / 2
  -> prove the requested mode before prompt insertion/write
  -> restore focus emulation
  -> ordinary browser-owned write
```

No `chrome.tabs.update(active=true)` or `Page.bringToFront` is used by this
selection path.

## Profile mapping

```text
FAST     -> INSTANT -> 0
BALANCED -> MEDIUM  -> 1
DEEP     -> HIGH    -> 2
MAX      -> unmapped
```

The exact slider fallback is intentionally retained. On authenticated fresh
background tabs it was the resolver that repeatedly proved the product slider.

## Fresh background keyboard proof

A zero-conversation-write probe was run on a runtime tab created directly as
`active:false`.

Observed result:

```text
runtime revision              PR17_2_BACKGROUND_PRODUCTION_R12
initial mode                  HIGH
slider focus mechanism        DOM.focus_exact
Home baseline proven          true
initial mode restored         true
conversation write count      0
tab activated                 false
runtime tab closed            true
debugger attached afterward   false
```

This isolated the production requirement that focus emulation must be enabled
before opening the reasoning picker on a never-active runtime tab.

## Fresh product-write proof

A one-write authenticated production smoke then proved the complete fresh-tab
path:

```text
fresh inactive runtime tab
-> HIGH -> INSTANT
-> strict prewrite selection proof
-> prompt insertion
-> background Enter commit
-> observed conversation write
-> canonical completion
```

The runtime tab remained inactive before, during, and after the write. No
automatic write retry occurred.

## Large-prompt / Codexia-class proof

A separate fresh-background one-write smoke used a 24,033-character prompt with
the `DEEP` profile.

Observed result:

```text
INSTANT -> HIGH
selectionStepCount = 2
DOM.focus_exact
write_event_observed = true
tab_activated_during_turn = false
foreground_activation_observed = false
canonical completion = true
automatic_write_retry = false
```

This proves that a substantial prompt is compatible with the repaired
background keyboard/submit path. It also narrows earlier
`CHATGPT_SUBMIT_NOT_OBSERVED:enter_fallback` specimens to the former
background-focus behavior rather than prompt size alone.

## Final three-profile production E2E

The bounded authenticated gate completed all three profile turns:

```text
FAST     -> INSTANT -> PASS
DEEP     -> HIGH    -> PASS
BALANCED -> MEDIUM  -> PASS
```

Final evidence:

- `write_attempts = 3`;
- `write_completions = 3`;
- `automatic_write_retry = false`;
- three distinct new-chat conversation ids;
- `background_mutation_count = 3`;
- every mutation proved focus emulation and stepwise selection;
- `conversationWriteBeforeSelection = false` for every turn;
- no tab activation or foreground activation was observed;
- canonical completion was proven for every turn;
- runtime revision matched `PR17_2_BACKGROUND_PRODUCTION_R12`.

CI for the final shipping head passed after formatting-only cleanup.

## Safety boundary

The production contract remains fail-closed:

- selected mode must be proven before conversation write;
- no automatic retry after an ambiguous protected write;
- no hidden fallback to a second selection mechanism after ambiguous mutation;
- no foreground activation for background selection/submit;
- no `MAX` synthesis from the three-state slider;
- no claim that reasoning/profile state is conversation-local or globally
  preserved without separate evidence.

## Remaining scope

PR17.2 proves **selection capability**, not cross-conversation preservation.

The final E2E explicitly reports:

```text
continuation_scope_tested = false
```

A separate scope experiment is still required:

```text
conversation A = HIGH
conversation B = MEDIUM
A -> INSTANT
prove A == INSTANT
prove B == MEDIUM (or observe otherwise)
fresh/new chat -> observe its independently hydrated mode
```

Until that evidence exists:

```text
model_selection        = AVAILABLE
reasoning_selection    = AVAILABLE
model_preservation     = UNKNOWN
reasoning_preservation = UNKNOWN
```

Tracks #197. PR #198 contains the shipping implementation and live gates.
