importScripts("service_worker_phase_timing_pr8_8.js");
importScripts("service_worker_instant_mode_pr8_8.js");
importScripts("service_worker_instant_unified_route_semantics_pr8_8.js");
importScripts("service_worker_instant_selection_repair_pr8_8.js");
importScripts("service_worker_instant_effort_selection.js");
importScripts("service_worker_model_profile_selection_pr8_10.js");
importScripts("service_worker_selection_lifecycle.js");
importScripts("service_worker_browser_response_stream.js");
importScripts("service_worker_early_response_completion.js");
importScripts("service_worker_observability_page_turn_lifecycle.js");
importScripts("service_worker_normalized_activity_stream_pr8_12.js");
importScripts("service_worker_response_lifecycle.js");
importScripts("service_worker_connector_lifecycle_pr10_0.js");
importScripts("service_worker_connector_router_characterization_pr10_0.js");
importScripts("service_worker_generated_artifact_pr10_1.js");

// PR15.16: closed PR10.1 artifact-shape characterization remains available in
// Git history/source-specific tests only; ordinary runtime contains no dormant
// import switch for those research overlays.

importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");
importScripts("service_worker_answer_channel_pr8_12.js");
importScripts("service_worker_temporary_chat_production_pr8_13.js");
importScripts("service_worker_temporary_session_identity_pr8_13.js");
importScripts("service_worker_temporary_fresh_identity_flush_pr8_13.js");
importScripts("service_worker_temporary_startup_readiness_pr8_13_2.js");
importScripts("service_worker_temporary_lifecycle.js");

async function _pr824aExistingRuntimeTabSnapshot() {
  const storedId = await storedRuntimeTabId();
  if (!Number.isInteger(storedId)) {
    return { tabId: null, preexisting: false };
  }
  try {
    const tab = await chrome.tabs.get(storedId);
    if (!isChatGPTUrl(tab?.url || "")) {
      return { tabId: null, preexisting: false };
    }
    return { tabId: storedId, preexisting: true };
  } catch {
    return { tabId: null, preexisting: false };
  }
}

async function _pr824aProvisioningObserverBefore() {
  const before = await _pr824aExistingRuntimeTabSnapshot();
  const activatedTabIds = new Set();
  const onActivated = (activeInfo) => {
    if (Number.isInteger(activeInfo?.tabId)) activatedTabIds.add(activeInfo.tabId);
  };
  chrome.tabs.onActivated.addListener(onActivated);
  return { before, activatedTabIds, onActivated };
}

async function _pr824aProvisioningObserverAfterSuccess(
  _message,
  result,
  context
) {
  const tabId = Number.isInteger(result?.tabId) ? result.tabId : null;
  let tabActiveAfter = null;
  if (tabId !== null) {
    try {
      const finalTab = await chrome.tabs.get(tabId);
      tabActiveAfter = Boolean(finalTab?.active);
    } catch {
      tabActiveAfter = null;
    }
  }

  const runtimeTabPreexisting = Boolean(
    context.before.preexisting && context.before.tabId === tabId
  );
  const runtimeTabCreatedForTurn = Boolean(
    tabId !== null && !runtimeTabPreexisting
  );
  const tabActivatedDuringTurn = Boolean(
    tabId !== null && context.activatedTabIds.has(tabId)
  );
  const foregroundActivationObserved = Boolean(
    result?.tabWasActive === true ||
    tabActiveAfter === true ||
    tabActivatedDuringTurn
  );

  return {
    ...result,
    runtimeTabPreexisting,
    runtimeTabCreatedForTurn,
    tabActiveAfter,
    tabActivatedDuringTurn,
    foregroundActivationObserved
  };
}

function _pr824aProvisioningObserverFinish(_message, context) {
  chrome.tabs.onActivated.removeListener(context.onActivated);
}

registerNativeTurnObserver("provisioning-observability", {
  before: _pr824aProvisioningObserverBefore,
  afterSuccess: _pr824aProvisioningObserverAfterSuccess,
  finish: _pr824aProvisioningObserverFinish
});

// Migration marker for the frozen PR11 source-order contract:
// _executeNativeTurnWithProvisioningObservability is now the explicit
// "provisioning-observability" registration above, not a runtime override.

// PR11.0: product chrome is read-only with respect to ChatGPT. It consumes only
// local bridge state and never participates in product-write/finality semantics.
importScripts("service_worker_product_surface_pr11_0.js");
