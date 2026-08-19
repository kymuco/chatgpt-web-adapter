importScripts("service_worker_phase_timing_pr8_8.js");
importScripts("service_worker_instant_mode_pr8_8.js");
importScripts("service_worker_instant_selection_repair_pr8_8.js");
importScripts("service_worker_retained_picker_forensics_pr8_8.js");
importScripts("service_worker_retained_route_identity_pr8_8.js");
importScripts("service_worker_orphan_lease_reconciliation_pr8_8.js");
importScripts("service_worker_instant_failure_forensics_pr8_8.js");
importScripts("service_worker_instant_popup_subtree_forensics_pr8_8.js");
importScripts("service_worker_picker_trigger_identity_pr8_8.js");
importScripts("service_worker_picker_trigger_poll_timeline_pr8_8.js");
importScripts("service_worker_picker_trigger_persistence_pr8_8.js");
importScripts("service_worker_reasoning_effort_slider_topology_pr8_8.js");
importScripts("service_worker_reasoning_effort_slider_governance_pr8_8.js");
importScripts("service_worker_reasoning_effort_slider_geometry_pr8_8.js");
importScripts("service_worker_instant_effort_slider_contract_pr8_8.js");
importScripts("service_worker_instant_effort_slider_key_pr8_8.js");
importScripts("service_worker_instant_effort_slider_selection_pr8_8.js");
importScripts("service_worker_instant_effort_activation_hardening_pr8_8.js");
importScripts("service_worker_instant_effort_dom_activation_pr8_8.js");
importScripts("service_worker_instant_effort_slider_support_pr8_8.js");

const _pr824aOriginalExecuteNativeTurn = executeNativeTurn;

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

executeNativeTurn = async function _executeNativeTurnWithProvisioningObservability(message) {
  const before = await _pr824aExistingRuntimeTabSnapshot();
  const activatedTabIds = new Set();
  const onActivated = (activeInfo) => {
    if (Number.isInteger(activeInfo?.tabId)) activatedTabIds.add(activeInfo.tabId);
  };
  chrome.tabs.onActivated.addListener(onActivated);

  try {
    const result = await _pr824aOriginalExecuteNativeTurn(message);
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

    const runtimeTabPreexisting = Boolean(before.preexisting && before.tabId === tabId);
    const runtimeTabCreatedForTurn = Boolean(tabId !== null && !runtimeTabPreexisting);
    const tabActivatedDuringTurn = Boolean(tabId !== null && activatedTabIds.has(tabId));
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
  } finally {
    chrome.tabs.onActivated.removeListener(onActivated);
  }
};
