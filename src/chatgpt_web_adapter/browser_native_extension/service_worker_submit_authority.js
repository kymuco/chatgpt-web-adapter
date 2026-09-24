// PR15.29 explicit submit-authority owner.
//
// Historical source-order composition was:
//
//   PR11.3 text hardening
//   -> schema7 atomic rich submit
//   -> closure repair
//   -> deadline repair
//   -> Temporary
//   -> base
//
// Preserve that exact outer-to-inner call graph without import-time hook
// reassignment.

async function submitOfficialPageTurn(debuggee, timeoutMs) {
  return _pr113SubmitOfficialTextWithoutPostCommitRetry(
    debuggee,
    timeoutMs,
    (textDebuggee, textTimeoutMs) =>
      _pr92Schema7AtomicAttachmentSubmit(
        textDebuggee,
        textTimeoutMs,
        (schema7Debuggee, schema7TimeoutMs) =>
          _pr92ClosurePageDeadlineGuardedSubmit(
            schema7Debuggee,
            schema7TimeoutMs,
            (closureDebuggee, closureTimeoutMs) =>
              _pr92SubmitOfficialPageTurnWithoutPostBoundaryRetry(
                closureDebuggee,
                closureTimeoutMs,
                (deadlineDebuggee, deadlineTimeoutMs) =>
                  _pr813SubmitOfficialPageTurn(
                    deadlineDebuggee,
                    deadlineTimeoutMs,
                    _cwaBaseSubmitOfficialPageTurn
                  )
              )
          )
      )
  );
}
