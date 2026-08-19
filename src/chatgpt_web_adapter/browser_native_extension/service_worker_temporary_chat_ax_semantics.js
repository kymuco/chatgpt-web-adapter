importScripts("service_worker_temporary_chat_state_semantics.js");

// PR8.7 live characterization #2:
// DOM-selected attributes and aria-label action semantics did not expose the
// current Temporary Chat selected state. Add an Accessibility Tree observation
// layer. Only bounded structural roles/state properties leave the browser.
// Accessible names and raw AX nodes remain browser-local.

const _pr87AxOriginalTemporaryControlSnapshot = _pr87TemporaryControlSnapshot;
let _pr87AxCaptureSnapshots = null;

function _pr87AxNormalize(value) {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return value.trim().toLowerCase();
  return value ?? null;
}

function _pr87AxStateValue(node, propertyName) {
  const properties = Array.isArray(node?.properties) ? node.properties : [];
  const property = properties.find((item) => item?.name === propertyName);
  return _pr87AxNormalize(property?.value?.value);
}

function _pr87AxBooleanState(value) {
  if (value === true || value === "true") return true;
  if (value === false || value === "false") return false;
  return null;
}

function _pr87AxSafeStateSignal(name, value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "boolean") return `${name}:${value ? "true" : "false"}`;
  if (typeof value !== "string") return null;
  const normalized = value.trim().toLowerCase();
  if (!normalized || normalized.length > 32) return null;
  if (!/^[a-z0-9_-]+$/.test(normalized)) return null;
  return `${name}:${normalized}`;
}

async function _pr87AxTemporarySnapshot(debuggee) {
  try {
    await _pr87RawSendCommand(debuggee, "Accessibility.enable");
    const tree = await _pr87RawSendCommand(debuggee, "Accessibility.getFullAXTree");
    const nodes = Array.isArray(tree?.nodes) ? tree.nodes : [];
    const actionableRoles = new Set([
      "button",
      "switch",
      "checkbox",
      "menuitemcheckbox",
      "menuitemradio",
      "radio",
      "tab"
    ]);
    const matchesTemporary = (value) => {
      if (typeof value !== "string") return false;
      const text = value.trim().toLowerCase().replace(/\s+/g, " ");
      return text.includes("temporary") || text.includes("временн");
    };

    const candidates = nodes.filter((node) => {
      if (node?.ignored === true) return false;
      return matchesTemporary(node?.name?.value);
    });
    const actionable = candidates.filter((node) => {
      const role = typeof node?.role?.value === "string"
        ? node.role.value.trim().toLowerCase()
        : "";
      return actionableRoles.has(role);
    });

    const roles = Array.from(new Set(
      candidates
        .map((node) => typeof node?.role?.value === "string"
          ? node.role.value.trim().toLowerCase()
          : "")
        .filter((value) => value && /^[a-z0-9_-]+$/.test(value))
    )).sort();

    const stateSignals = [];
    let selectionState = null;
    let selectionProofSignals = [];

    if (actionable.length === 1) {
      const node = actionable[0];
      const explicitSelectionStates = [];
      for (const propertyName of ["pressed", "checked", "selected"]) {
        const rawValue = _pr87AxStateValue(node, propertyName);
        const signal = _pr87AxSafeStateSignal(propertyName, rawValue);
        if (signal) stateSignals.push(signal);
        const booleanValue = _pr87AxBooleanState(rawValue);
        if (booleanValue !== null) {
          explicitSelectionStates.push({ propertyName, value: booleanValue });
        }
      }

      for (const propertyName of ["expanded", "haspopup", "disabled", "focused"]) {
        const signal = _pr87AxSafeStateSignal(
          propertyName,
          _pr87AxStateValue(node, propertyName)
        );
        if (signal) stateSignals.push(signal);
      }

      const trueStates = explicitSelectionStates.filter((item) => item.value === true);
      const falseStates = explicitSelectionStates.filter((item) => item.value === false);
      if (trueStates.length > 0 && falseStates.length === 0) {
        selectionState = true;
        selectionProofSignals = trueStates.map(
          (item) => `ax:${item.propertyName}:true`
        );
      } else if (falseStates.length > 0 && trueStates.length === 0) {
        selectionState = false;
      } else if (trueStates.length > 0 && falseStates.length > 0) {
        stateSignals.push("selection-source-conflict");
      }
    }

    return {
      candidateCount: candidates.length,
      actionableCandidateCount: actionable.length,
      roles,
      stateSignals: Array.from(new Set(stateSignals)).sort(),
      selectionState,
      selectionProofSignals
    };
  } catch {
    return {
      candidateCount: 0,
      actionableCandidateCount: 0,
      roles: [],
      stateSignals: ["ax-probe-failed"],
      selectionState: null,
      selectionProofSignals: []
    };
  }
}

_pr87TemporaryControlSnapshot = async function _pr87TemporaryControlSnapshotWithAX(debuggee) {
  const domSnapshot = await _pr87AxOriginalTemporaryControlSnapshot(debuggee);
  const axSnapshot = await _pr87AxTemporarySnapshot(debuggee);

  if (Array.isArray(_pr87AxCaptureSnapshots)) {
    _pr87AxCaptureSnapshots.push(axSnapshot);
  }

  const domSelected = typeof domSnapshot?.selected === "boolean"
    ? domSnapshot.selected
    : null;
  const axSelected = typeof axSnapshot?.selectionState === "boolean"
    ? axSnapshot.selectionState
    : null;

  let selected = domSelected;
  let proofSignals = Array.isArray(domSnapshot?.proofSignals)
    ? [...domSnapshot.proofSignals]
    : [];
  const stateSignals = Array.isArray(domSnapshot?.stateSignals)
    ? [...domSnapshot.stateSignals]
    : [];

  stateSignals.push(...axSnapshot.stateSignals.map((signal) => `ax:${signal}`));

  if (domSelected !== null && axSelected !== null && domSelected !== axSelected) {
    selected = null;
    proofSignals = [];
    stateSignals.push("selection-source-conflict:dom-vs-ax");
  } else if (axSelected !== null) {
    selected = axSelected;
    if (axSelected === true) {
      proofSignals.push(...axSnapshot.selectionProofSignals);
    }
  }

  return {
    ...domSnapshot,
    selected,
    proofSignals: Array.from(new Set(proofSignals)),
    stateSignals: Array.from(new Set(stateSignals)),
    axSnapshot
  };
};

const _pr87AxPriorExecuteNativeTurn = executeNativeTurn;
executeNativeTurn = async function _executeNativeTurnWithTemporaryAXEvidence(message) {
  if (message?.probeTemporaryMode !== true) {
    return _pr87AxPriorExecuteNativeTurn(message);
  }

  _pr87AxCaptureSnapshots = [];
  try {
    const result = await _pr87AxPriorExecuteNativeTurn(message);
    const snapshots = _pr87AxCaptureSnapshots;
    const before = snapshots.length > 0 ? snapshots[0] : null;
    const after = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;
    return {
      ...result,
      axBefore: before,
      axAfter: after,
      temporaryStateSemantics: "accessibility_tree_v1"
    };
  } finally {
    _pr87AxCaptureSnapshots = null;
  }
};
