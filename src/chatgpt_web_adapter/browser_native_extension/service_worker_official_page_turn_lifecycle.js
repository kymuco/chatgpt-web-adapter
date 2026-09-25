// Single active official-page-turn composition owner.
//
// Every domain exposes a named page-turn function. The runtime assembles the
// exact historical graph once, including the two deliberate rich-input bypasses:
// schema19 new-chat bypasses schema18, and schema29 bypasses schema20.

async function _cwaOfficialPageTurnObservability(args) {
  return _executeOfficialPageTurnWithObservabilityLifecycle(args);
}

async function _cwaOfficialPageTurnTemporary(args) {
  return _pr813ExecuteOfficialPageTurnWithSessionIdentity(
    args,
    _cwaOfficialPageTurnObservability
  );
}

async function _cwaOfficialPageTurnRichBase(args) {
  return _pr92ExecuteOfficialPageTurnWithinTurn(
    args,
    _cwaOfficialPageTurnTemporary
  );
}

async function _cwaOfficialPageTurnSchema16(args) {
  return _pr92Schema16ExecuteOfficialPageTurnWithinTurn(
    args,
    _cwaOfficialPageTurnRichBase
  );
}

async function _cwaOfficialPageTurnSchema17(args) {
  return _pr92Schema17ExecuteOfficialPageTurnWithinTurn(
    args,
    _cwaOfficialPageTurnSchema16
  );
}

async function _cwaOfficialPageTurnSchema18(args) {
  return _pr92Schema18ExecuteOfficialPageTurnWithIdentityAuthority(
    args,
    _cwaOfficialPageTurnSchema17
  );
}

async function _cwaOfficialPageTurnSchema19(args) {
  return _pr92Schema19ExecuteOfficialPageTurnWithRequestBoundIdentity(
    args,
    _cwaOfficialPageTurnSchema18,
    _cwaOfficialPageTurnSchema17
  );
}

async function _cwaOfficialPageTurnSchema20(args) {
  return _pr92Schema20ExecuteOfficialPageTurnWithSubmitBoundRequest(
    args,
    _cwaOfficialPageTurnSchema19
  );
}

async function _cwaOfficialPageTurnSchema29(args) {
  return _pr92Schema29ExecuteOfficialPageTurn(
    args,
    _cwaOfficialPageTurnSchema20,
    _cwaOfficialPageTurnSchema19
  );
}

async function _cwaOfficialPageTurnOrdinaryIdentity(args) {
  return _cwaOrdinaryIdentityExecuteOfficialPageTurn(
    args,
    _cwaOfficialPageTurnSchema29
  );
}

async function executeOfficialPageTurn(args) {
  return _cwaOfficialPageTurnOrdinaryIdentity(args);
}
