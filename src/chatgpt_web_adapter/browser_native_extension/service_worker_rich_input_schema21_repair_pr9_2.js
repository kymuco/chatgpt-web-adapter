// PR9.2 schema-21 validated-click-boundary submit-arm closure.
//
// Loaded after schema 20. Schema 20 moved conversation-request authority into the
// same renderer task as schema-7's atomic attachment validation and click, but its
// wrapper emitted the page-side arm marker before schema 7 had completed the
// deadline, attachment-evidence, and Send-button checks. A failed validation could
// therefore leave request authority armed during the later observation window.
//
// Schema 21 bypasses only schema 20's early-marker expression wrapper and starts
// again from the immutable schema-7 expression captured by schema 20. The unique
// marker is injected exactly once immediately before button.click(), after every
// schema-7 validation and the final page-side deadline check have succeeded. The
// marker and click remain synchronous in the same Runtime.evaluate page task.

const PR92_SCHEMA21_REPAIR_SCHEMA = 21;
const PR92_SCHEMA21_ARM_BOUNDARY =
  "AFTER_ALL_VALIDATION_IMMEDIATELY_BEFORE_BUTTON_CLICK";
const PR92_SCHEMA21_CLICK_NEEDLE = "    button.click();";

function _pr92Schema21ValidatedClickBoundaryArm(
  selector,
  deadlineEpochMs,
  expectedNames
) {
  // Deliberately bypass schema 20's early-marker helper and start from the
  // immutable schema-7 builder, which contains no pre-validation marker.
  const expression = _pr92Schema7BaseAtomicAttachmentSubmitExpression(
    selector,
    deadlineEpochMs,
    expectedNames
  );
  const context = _pr92ActiveRichInputContext;
  if (context === null) return expression;

  const firstClick = expression.indexOf(PR92_SCHEMA21_CLICK_NEEDLE);
  const secondClick =
    firstClick < 0
      ? -1
      : expression.indexOf(PR92_SCHEMA21_CLICK_NEEDLE, firstClick + 1);
  if (firstClick < 0 || secondClick >= 0) {
    throw new Error("PR9_2_SCHEMA21_ATOMIC_CLICK_BOUNDARY_NOT_UNIQUE");
  }

  const encodedMarker = JSON.stringify(context.schema20ProtectedSubmitMarker);
  const markerStatement =
    `    try { console.debug(${encodedMarker}); } catch {}\n`;
  return (
    expression.slice(0, firstClick) +
    markerStatement +
    expression.slice(firstClick)
  );
}

function _pr92Schema21AugmentSupportResult(result) {
  return {
    ...result,
    richInputSchemaVersion: PR92_SCHEMA21_REPAIR_SCHEMA,
    protectedSubmitArmBoundary: PR92_SCHEMA21_ARM_BOUNDARY,
    protectedSubmitArmAfterAllValidation: true,
    preValidationSubmitArmPossible: false
  };
}
