// PR8.12 patch-protocol compatibility hardening.
//
// The proven PR8.9 product stream can append text with either an explicit
// /message/content/parts/0 path or a compact null path after selecting the
// current message. Keep PR8.12 activity text aligned with that behavior.

const _pr812PatchProtocolPriorPatchSelect = _pr812PatchSelect;
const _pr812PatchProtocolPriorPatchApplyItem = _pr812PatchApplyItem;

_pr812PatchSelect = function _pr812PatchSelectWithStableSyntheticId(state, message) {
  if (!message || typeof message !== "object") return;
  let selected = message;
  if (!_pr812OptionalString(message.id)) {
    state.syntheticCounter += 1;
    selected = {
      ...message,
      id: `pr812-patch-${state.syntheticCounter}`
    };
  }
  _pr812PatchProtocolPriorPatchSelect(state, selected);
};

_pr812PatchApplyItem = function _pr812PatchApplyItemWithCompactNullPath(
  context,
  state,
  item
) {
  if (!item || typeof item !== "object") return;
  const path = typeof item.p === "string" ? item.p : null;
  const value = item.v;

  if (
    path === null &&
    typeof value === "string" &&
    value.length > 0 &&
    state.currentPatchMessage
  ) {
    const content = state.currentPatchMessage.content || {};
    const parts = Array.isArray(content.parts) ? [...content.parts] : [];
    const previous = typeof parts[0] === "string" ? parts[0] : "";
    parts[0] = previous + value;
    state.currentPatchMessage.content = { ...content, parts };
    _pr812InspectMessage(context, state, state.currentPatchMessage);
    return;
  }

  return _pr812PatchProtocolPriorPatchApplyItem(context, state, item);
};
