// Ordinary-text committed-identity error preservation boundary.
//
// PR14.1 ordinary identity authority intentionally reuses the historical
// PR9_2_WRITE_COMPLETED_CONVERSATION_ID_UNRESOLVED prefix so Python preserves the
// existing committed-write / reconciliation-required / no-retry semantics.
// Historical rich-input executeNativeTurn wrappers also recognize that prefix.
// When an ordinary PR14.1 failure bubbles through those older wrappers they can
// replace the exact ordinary suffix with non-authoritative rich diagnostics.
//
// This final write-domain layer records only the exact error already created by
// the ordinary authority. If an inner wrapper later rewrites the same committed
// prefix, restore the recorded ordinary detail before the result leaves the
// extension. It introduces no new authority, identity source, retry, fallback,
// or product write.

const CWA_ORDINARY_IDENTITY_ERROR_BOUNDARY_SCHEMA = 1;
const _cwaOrdinaryIdentityErrorBoundaryPriorFactory = _cwaOrdinaryIdentityError;
const _cwaOrdinaryIdentityErrorBoundaryPriorExecuteNativeTurn = executeNativeTurn;

let _cwaOrdinaryIdentityExactCommittedFailure = null;

_cwaOrdinaryIdentityError = function _cwaOrdinaryIdentityPreservedError(
  suffix,
  diagnostics = null
) {
  const error = _cwaOrdinaryIdentityErrorBoundaryPriorFactory(suffix, diagnostics);
  const detail = error instanceof Error ? error.message : String(error);
  if (detail.startsWith(`${CWA_ORDINARY_IDENTITY_COMMITTED_ERROR}:`)) {
    _cwaOrdinaryIdentityExactCommittedFailure = detail;
  }
  return error;
};

executeNativeTurn = async function _cwaOrdinaryIdentityErrorBoundaryExecuteNativeTurn(
  message
) {
  if (!_cwaOrdinaryIdentityEligible(message)) {
    return _cwaOrdinaryIdentityErrorBoundaryPriorExecuteNativeTurn(message);
  }

  _cwaOrdinaryIdentityExactCommittedFailure = null;
  try {
    return await _cwaOrdinaryIdentityErrorBoundaryPriorExecuteNativeTurn(message);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    const exact = _cwaOrdinaryIdentityExactCommittedFailure;
    if (
      typeof exact === "string" &&
      exact.startsWith(`${CWA_ORDINARY_IDENTITY_COMMITTED_ERROR}:`) &&
      detail.startsWith(CWA_ORDINARY_IDENTITY_COMMITTED_ERROR)
    ) {
      throw new Error(exact);
    }
    throw error;
  } finally {
    _cwaOrdinaryIdentityExactCommittedFailure = null;
  }
};
