// PR15.48 explicit optional post-write owner.
//
// Schema17 introduced bounded non-authoritative post-write diagnostics.
// Schema18 tightened their budget to preserve conversation-identity resolution.
// Schema19 is the final effective policy: new-chat exact-request response-body
// reads get a causal-identity budget; all other diagnostics delegate to schema18.

async function _pr92Schema17OptionalPostWrite(
  context,
  stage,
  operation,
  capMs = PR92_SCHEMA17_OPTIONAL_POSTWRITE_CAP_MS
) {
  return _pr92Schema19OptionalPostWrite(context, stage, operation, capMs);
}
