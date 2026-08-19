importScripts("service_worker_temporary_chat.js");

// PR8.7 live probe repair: current ChatGPT exposed the Temporary control only
// through aria-label, without aria-pressed/data-state selected attributes.
// Treat accessibility action semantics as explicit state evidence when the
// label unambiguously describes the action that would change the current mode.
// Raw aria-label text still never leaves the browser context.

_pr87TemporaryControlSnapshotExpression = function _pr87TemporaryControlSnapshotExpressionWithAriaActionState() {
  return `(() => {
    const normalize = (value) => typeof value === 'string'
      ? value.trim().toLowerCase().replace(/\\s+/g, ' ')
      : '';
    const matchesTemporary = (value) => {
      const text = normalize(value);
      return text.includes('temporary') || text.includes('временн');
    };
    const explicitTrueStates = new Set(['on', 'checked', 'active', 'selected']);
    const explicitFalseStates = new Set(['off', 'unchecked', 'inactive', 'unselected']);

    const classifyAriaLabelActionState = (value) => {
      const text = normalize(value);
      if (!matchesTemporary(text)) return { selected: null, signal: null };

      // Accessibility labels commonly describe the action that activation will
      // perform. If the available action is to turn Temporary Chat OFF, then
      // Temporary is currently selected. Conversely, a turn-ON action means
      // the mode is currently not selected.
      const selectedActionPatterns = [
        ['turn off', 'aria-label:turn-off-action'],
        ['switch off', 'aria-label:switch-off-action'],
        ['disable', 'aria-label:disable-action'],
        ['deactivate', 'aria-label:deactivate-action'],
        ['leave temporary', 'aria-label:leave-temporary-action'],
        ['exit temporary', 'aria-label:exit-temporary-action'],
        ['выключ', 'aria-label:ru-turn-off-action'],
        ['отключ', 'aria-label:ru-disable-action']
      ];
      const unselectedActionPatterns = [
        ['turn on', 'aria-label:turn-on-action'],
        ['switch on', 'aria-label:switch-on-action'],
        ['enable', 'aria-label:enable-action'],
        ['activate', 'aria-label:activate-action'],
        ['start temporary', 'aria-label:start-temporary-action'],
        ['включ', 'aria-label:ru-turn-on-action']
      ];

      for (const [pattern, signal] of selectedActionPatterns) {
        if (text.includes(pattern)) return { selected: true, signal };
      }
      for (const [pattern, signal] of unselectedActionPatterns) {
        if (text.includes(pattern)) return { selected: false, signal };
      }
      return { selected: null, signal: 'aria-label:temporary-neutral' };
    };

    const candidates = [];
    for (const element of Array.from(document.querySelectorAll('button,[role="button"]'))) {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      if (rect.width <= 0 || rect.height <= 0 || style.visibility === 'hidden' || style.display === 'none') {
        continue;
      }

      const fields = {
        text: element.innerText || element.textContent || '',
        aria_label: element.getAttribute('aria-label') || '',
        title: element.getAttribute('title') || '',
        data_testid: element.getAttribute('data-testid') || ''
      };
      const matchSignals = Object.entries(fields)
        .filter(([, value]) => matchesTemporary(value))
        .map(([name]) => name);
      if (!matchSignals.length) continue;

      const proofSignals = [];
      const falseSignals = [];
      const stateSignals = [];
      const ariaPressed = normalize(element.getAttribute('aria-pressed'));
      const ariaChecked = normalize(element.getAttribute('aria-checked'));
      const ariaCurrent = normalize(element.getAttribute('aria-current'));
      const dataState = normalize(element.getAttribute('data-state'));
      const dataSelected = normalize(element.getAttribute('data-selected'));

      if (ariaPressed === 'true') proofSignals.push('aria-pressed:true');
      else if (ariaPressed === 'false') falseSignals.push('aria-pressed:false');
      if (ariaChecked === 'true') proofSignals.push('aria-checked:true');
      else if (ariaChecked === 'false') falseSignals.push('aria-checked:false');
      if (ariaCurrent === 'true') proofSignals.push('aria-current:true');
      if (explicitTrueStates.has(dataState)) proofSignals.push('data-state:' + dataState);
      else if (explicitFalseStates.has(dataState)) falseSignals.push('data-state:' + dataState);
      if (dataSelected === 'true') proofSignals.push('data-selected:true');
      else if (dataSelected === 'false') falseSignals.push('data-selected:false');

      const ariaActionState = classifyAriaLabelActionState(fields.aria_label);
      if (ariaActionState.signal) stateSignals.push(ariaActionState.signal);
      if (ariaActionState.selected === true) proofSignals.push(ariaActionState.signal);
      else if (ariaActionState.selected === false) falseSignals.push(ariaActionState.signal);

      const selected = proofSignals.length
        ? true
        : (falseSignals.length ? false : null);
      candidates.push({
        matchSignals,
        proofSignals,
        stateSignals,
        selected,
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2
      });
    }

    const primary = candidates.length === 1 ? candidates[0] : null;
    return {
      candidateCount: candidates.length,
      controlFound: candidates.length > 0,
      ambiguous: candidates.length > 1,
      selected: primary ? primary.selected : null,
      matchSignals: primary ? primary.matchSignals : [],
      proofSignals: primary ? primary.proofSignals : [],
      stateSignals: primary ? primary.stateSignals : [],
      point: primary ? { x: primary.x, y: primary.y } : null
    };
  })()`;
};

// Add the newly observed safe structural state signal to probe results without
// changing normal production turn behavior.
const _pr87PriorExecuteNativeTurnStateSemantics = executeNativeTurn;
executeNativeTurn = async function _executeNativeTurnWithTemporaryStateSignalResult(message) {
  const result = await _pr87PriorExecuteNativeTurnStateSemantics(message);
  if (message?.probeTemporaryMode !== true || !result || typeof result !== "object") {
    return result;
  }

  // Re-observe only the already-open probe flow through the existing result.
  // The underlying probe closes its isolated tab before returning, so no raw
  // label or additional page data is exported here. proofSignals already carry
  // the action-semantic evidence when it proves selection.
  return {
    ...result,
    temporaryStateSemantics: "aria_label_action_v1"
  };
};
