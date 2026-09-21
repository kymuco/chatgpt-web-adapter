// Explicit rich-input page-turn graph owner.
//
// The rich-input schemas are not a purely linear wrapper chain. Schema 19
// intentionally bypasses schema 18 for new-chat causal identity, and schema 29
// intentionally bypasses schema 20's obsolete post-return decision while
// retaining schema 19. Those dependencies are wired here explicitly.
const _cwaRichInputPageTurnBase = executeOfficialPageTurn;

async function _cwaRichInputBasePageTurn(args) {
  return _pr92ExecuteOfficialPageTurnWithinTurn(
    args,
    _cwaRichInputPageTurnBase
  );
}

async function _cwaRichInputSchema16PageTurn(args) {
  return _pr92Schema16ExecuteOfficialPageTurnWithinTurn(
    args,
    _cwaRichInputBasePageTurn
  );
}

async function _cwaRichInputSchema17PageTurn(args) {
  return _pr92Schema17ExecuteOfficialPageTurnWithinTurn(
    args,
    _cwaRichInputSchema16PageTurn
  );
}

async function _cwaRichInputSchema18PageTurn(args) {
  return _pr92Schema18ExecuteOfficialPageTurnWithIdentityAuthority(
    args,
    _cwaRichInputSchema17PageTurn
  );
}

async function _cwaRichInputSchema19PageTurn(args) {
  return _pr92Schema19ExecuteOfficialPageTurnWithRequestBoundIdentity(
    args,
    _cwaRichInputSchema18PageTurn,
    _cwaRichInputSchema17PageTurn
  );
}

async function _cwaRichInputSchema20PageTurn(args) {
  return _pr92Schema20ExecuteOfficialPageTurnWithSubmitBoundRequest(
    args,
    _cwaRichInputSchema19PageTurn
  );
}

async function _cwaRichInputSchema29PageTurn(args) {
  return _pr92Schema29ExecuteOfficialPageTurn(
    args,
    _cwaRichInputSchema20PageTurn,
    _cwaRichInputSchema19PageTurn
  );
}

executeOfficialPageTurn = async function _executeOfficialPageTurnWithRichInputGraph(args) {
  return _cwaRichInputSchema29PageTurn(args);
};
