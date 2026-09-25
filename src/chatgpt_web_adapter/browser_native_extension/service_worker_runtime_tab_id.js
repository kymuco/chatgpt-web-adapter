// PR15.43 explicit runtime-tab-id owner.
//
// Bootstrap/native hello deliberately reads the persisted id through the
// immutable base helper before reconciliation is installed. Once the runtime
// assembly loads, every ordinary consumer resolves this public owner and gets
// live validation / stale-state repair.

async function storedRuntimeTabId() {
  return _pr824a3StoredRuntimeTabIdWithLiveValidation();
}
