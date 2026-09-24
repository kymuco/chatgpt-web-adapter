// PR15.25 explicit composer/model-selection preparation owner.
//
// Replaces the historical source-ordered locateAndFocusComposer wrappers from
// model-profile selection, Instant selection repair, and Instant observation.
// The order is outer -> inner and matches the pre-consolidation wrapper chain.

const _cwaSelectionPreparationPriorLocateAndFocusComposer = locateAndFocusComposer;

locateAndFocusComposer =
  async function _cwaLocateAndFocusComposerWithSelectionPreparation(debuggee) {
    await _pr810PrepareComposer(debuggee);
    await _pr88SelectionPrepareComposer(debuggee);
    await _pr88InstantObserveComposerBeforeWrite(debuggee);
    return _cwaSelectionPreparationPriorLocateAndFocusComposer(debuggee);
  };
