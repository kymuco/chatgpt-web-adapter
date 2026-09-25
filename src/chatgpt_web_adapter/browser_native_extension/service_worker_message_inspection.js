// PR15.34 explicit message-inspection owner.
//
// Historical shipping composition progressively wrapped _pr812InspectMessage:
// PR8.12 base response activity, PR15.22 product observation, then PR9.3
// structured source/citation observation. Keep that side-effect order explicit
// without runtime reassignment or prior-function capture.

function _pr812InspectMessage(context, state, message) {
  _pr812BaseInspectMessage(context, state, message);
  _pr10ProductObservationInspectMessage(context, state, message);
  _pr93InspectMessage(context, state, message);
}
