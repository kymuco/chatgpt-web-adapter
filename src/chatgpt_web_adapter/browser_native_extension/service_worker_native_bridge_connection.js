// PR15.40 explicit native-bridge connection owner.
//
// Initial extension bootstrap deliberately calls _cwaBaseConnectNativeBridge()
// before the PR11 product surface is loaded. Once product state helpers exist,
// all subsequent reconnect/startup/install calls resolve this public owner.

function connectNativeBridge() {
  return _cwaConnectNativeBridgeWithProductState();
}
