locateAndFocusComposer =
  async function _locateAndFocusComposerWithPickerTriggerTimeline(debuggee) {
    try {
      return await _pr88TriggerPriorLocateAndFocusComposer(debuggee);
    } catch (error) {
      const context = _pr88TriggerTimelineContext;
      if (context !== null && _pr88TriggerLeaseId(context.leaseId) !== null) {
        try {
          await _pr88TriggerPersist(error, context, debuggee);
        } catch {
          // Timeline persistence must never replace or mask the original failure.
        }
      }
      throw error;
    }
  };

async function _pr88TriggerStoredRecord() {
  try {
    const stored = await chrome.storage.local.get(
      PR88_PICKER_TRIGGER_TIMELINE_STORAGE_KEY
    );
    const value = stored?.[PR88_PICKER_TRIGGER_TIMELINE_STORAGE_KEY];
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}
