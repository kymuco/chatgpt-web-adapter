// PR15.35 explicit protected-submit expression owner.
//
// Historical rich-input schemas evolved the page-side protected-submit builder
// from schema 7's atomic validation/click expression through schema 20's early
// arm-marker wrapper to schema 21's corrected validated-click-boundary arm.
//
// Production uses the schema-21 semantics explicitly. Historical helpers remain
// named stages and no longer replace the shared public builder by source order.

function _pr92Schema7AtomicAttachmentSubmitExpression(
  selector,
  deadlineEpochMs,
  expectedNames
) {
  return _pr92Schema21ValidatedClickBoundaryArm(
    selector,
    deadlineEpochMs,
    expectedNames
  );
}
