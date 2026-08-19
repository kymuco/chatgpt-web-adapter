// PR8.8 selection record enrichment and support RPC.

const _pr88InstantEffortPriorSelectionRecord = _pr88SelectionRecord;
const _pr88InstantEffortPriorExecuteNativeTurn = executeNativeTurn;

_pr88SelectionRecord = function _pr88SelectionRecordWithEffortSlider(context) {
  const base = _pr88InstantEffortPriorSelectionRecord(context);
  const finite = (value) => Number.isFinite(value) ? value : null;
  return {
    ...base,
    instantEffortSelectionSchemaVersion:
      context.instantEffortSelectionSchemaVersion || PR88_INSTANT_EFFORT_SELECTION_SCHEMA_VERSION,
    selectionMechanism: context.selectionMechanism || null,
    instantEffortPickerClickPerformed: context.instantEffortPickerClickPerformed === true,
    effortSliderCandidateCount: Number.isInteger(context.effortSliderCandidateCount)
      ? context.effortSliderCandidateCount : 0,
    effortSliderAriaValueMin: finite(context.effortSliderAriaValueMin),
    effortSliderAriaValueMax: finite(context.effortSliderAriaValueMax),
    effortSliderAriaValueNowBefore: finite(context.effortSliderAriaValueNowBefore),
    effortSliderAriaValueNowAfter: finite(context.effortSliderAriaValueNowAfter),
    effortSliderStepCount: Number.isInteger(context.effortSliderStepCount)
      ? context.effortSliderStepCount : null,
    effortSliderFocusProven: context.effortSliderFocusProven === true,
    effortSliderHomeDispatched: context.effortSliderHomeDispatched === true,
    effortSliderMinReachedProven: context.effortSliderMinReachedProven === true,
    effortSliderObservedAfterHome: context.effortSliderObservedAfterHome === true,
    advancedControlClicked: context.advancedControlClicked === true,
    modelControlClicked: context.modelControlClicked === true
  };
};

executeNativeTurn = async function _executeNativeTurnWithInstantEffortSelectionSupport(message) {
  if (message?.characterizeInstantEffortSelectionSupport === true) {
    if (_pr88InstantEffortSupportConflict(message)) {
      throw new Error("PR8_8_INSTANT_EFFORT_SUPPORT_FLAG_CONFLICT");
    }
    return {
      instantEffortSelectionSupported: true,
      instantEffortSelectionSchemaVersion: PR88_INSTANT_EFFORT_SELECTION_SCHEMA_VERSION,
      productionInstantWorkingPathSupported: true,
      quickPickerOnly: true,
      exactDiscreteRangeRequired: true,
      semanticHomeKeySelectionSupported: true,
      selectedInstantProofRequired: true,
      preInputFailureBoundaryPreserved: true,
      advancedPickerClickForbidden: true,
      modelControlClickForbidden: true,
      automaticRetry: false
    };
  }
  return _pr88InstantEffortPriorExecuteNativeTurn(message);
};
