// PR9.2 schema-14 rich-input/model-profile composition guard.
//
// Loaded after schema 13. PR9.2 proves one total deadline for the browser-owned
// rich-input path, while the independently proven PR8.10 model-profile selector
// still owns fixed/raw prewrite waits and CDP input operations. A turn carrying
// both attachment paths and requiredModelMode would therefore compose two proven
// features without a proven shared deadline. This layer fails that *new*
// combination closed before staging or write rather than widening PR8.10 inside
// PR9.2. Text-only model-profile turns and ordinary rich-input turns are unchanged.

const _pr92Schema14PriorExecuteNativeTurn = executeNativeTurn;
const PR92_SCHEMA14_REPAIR_SCHEMA = 14;

function _pr92Schema14HasAttachmentPaths(message) {
  return Array.isArray(message?.attachmentPaths) && message.attachmentPaths.length > 0;
}

function _pr92Schema14HasModelProfileRequirement(message) {
  return typeof message?.requiredModelMode === "string" && Boolean(message.requiredModelMode.trim());
}

executeNativeTurn = async function _executeNativeTurnWithPr92Schema14CompositionGuard(message) {
  if (
    message?.characterizeRichInputSupport !== true &&
    _pr92Schema14HasAttachmentPaths(message) &&
    _pr92Schema14HasModelProfileRequirement(message)
  ) {
    // This guard is intentionally outside the schema-13/prior chain. No PR9.2
    // turn context, durable fence, attachment staging, model-selector mutation,
    // or protected conversation write has been entered when this error is raised.
    throw new Error("PR9_2_RICH_INPUT_MODEL_PROFILE_COMBINATION_UNAVAILABLE");
  }

  const result = await _pr92Schema14PriorExecuteNativeTurn(message);
  if (message?.characterizeRichInputSupport !== true) return result;
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA14_REPAIR_SCHEMA,
    richInputModelProfileCombinationSupported: false,
    richInputModelProfileCombinationFailsBeforeStaging: true,
    richInputModelProfileCombinationFailsBeforeWrite: true,
    pr810RawPrewriteSelectorExcludedFromRichInput: true
  };
};
