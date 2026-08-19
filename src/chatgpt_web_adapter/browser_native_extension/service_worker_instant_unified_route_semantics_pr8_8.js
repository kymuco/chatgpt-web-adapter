// PR8.8 unified GPT-5.6 route semantics and model-slug false-reasoning dealiasing.
//
// Model identity and reasoning state are separate evidence dimensions. In current
// ChatGPT, model identifiers such as "gpt-5-6-thinking" may appear in response
// metadata while the independently proven composer effort remains INSTANT.
// Therefore a model/model_slug value containing "thinking" is not, by itself,
// evidence that the product routed the turn through Medium/High reasoning.
//
// Positive reasoning-route evidence remains fail-closed: an explicit reasoning/
// thinking key that resolves ON (or is present with no explicit OFF state) still
// classifies the route as reasoning. Raw prompt/response content is unchanged and
// remains outside this bounded metadata layer.

const PR88_UNIFIED_GPT56_ROUTE_STATUS =
  "UNIFIED_GPT_5_6_ROUTE_WITHOUT_EXPLICIT_REASONING";

function _pr88UnifiedGpt56Identifier(value) {
  if (typeof value !== "string") return false;
  const text = value.trim().toLowerCase();
  return /^gpt-5-6(?:$|[-_.:/])/.test(text);
}

function _pr88UnifiedModelSlugReasoningAlias(value) {
  if (!_pr88UnifiedGpt56Identifier(value)) return false;
  const text = value.trim().toLowerCase();
  return text.includes("thinking") || text.includes("reasoning");
}

_pr88InstantDeriveNetworkRoute =
  function _pr88InstantDeriveNetworkRouteWithUnifiedGpt56Semantics(
    requestHints,
    responseHints
  ) {
    const merged = _pr88InstantNewHintAccumulator();
    _pr88InstantMergeHints(merged, requestHints);
    _pr88InstantMergeHints(merged, responseHints);

    const reasoning = merged.reasoningStates;
    const explicitReasoningMetadataObserved = merged.reasoningHintKeys.size > 0;
    const reasoningOff = reasoning.has("OFF");

    // A model slug is model identity evidence, not reasoning-state evidence.
    // If an explicit reasoning/thinking key exists but is not explicitly OFF,
    // stay conservative and treat it as a positive reasoning-route observation.
    const explicitReasoningPositive =
      reasoning.has("ON") ||
      (explicitReasoningMetadataObserved && !reasoningOff);

    const instantPositive = merged.modelModes.has("INSTANT");
    const identifiers = Array.from(merged.modelIdentifiers);
    const unifiedGpt56Observed = identifiers.some(_pr88UnifiedGpt56Identifier);
    const modelSlugReasoningAliasObserved =
      identifiers.some(_pr88UnifiedModelSlugReasoningAlias);

    let status = "INCONCLUSIVE";
    if (explicitReasoningPositive) {
      status = "REASONING_ROUTE_OBSERVED";
    } else if (instantPositive) {
      status = "INSTANT_MODEL_ROUTE_OBSERVED";
    } else if (reasoningOff) {
      status = "NO_REASONING_EXPLICITLY_OBSERVED";
    } else if (unifiedGpt56Observed) {
      status = PR88_UNIFIED_GPT56_ROUTE_STATUS;
    }

    return {
      status,
      instantModelRouteObserved: instantPositive,
      reasoningRouteObserved: explicitReasoningPositive,
      reasoningOffObserved: reasoningOff,
      // This legacy field stays strict: a unified GPT-5.6 identity without
      // explicit reasoning metadata is compatible with INSTANT, but model
      // identity alone does not prove "no reasoning" at the network layer.
      noReasoningRouteProven: (
        status === "INSTANT_MODEL_ROUTE_OBSERVED" ||
        status === "NO_REASONING_EXPLICITLY_OBSERVED"
      ),
      unifiedGpt56RouteObserved: unifiedGpt56Observed,
      modelSlugReasoningAliasObserved
    };
  };
