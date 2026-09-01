// PR10.0: outermost no-write connector observation support probes.
//
// The connector message-observation overlay is intentionally loaded inside the
// normalized activity stream, but PR9.2 rich-input wrappers are loaded later by
// the manifest entrypoint. Characterization must therefore sit outside the full
// production stack so no-write flags can never enter rich-input preflight as an
// ordinary product turn.
//
// These probes never type, submit, stage attachments, click controls, acquire
// write/approval authority, change canonical finality, retry, or select a fallback.

const _pr100SupportPriorExecuteNativeTurn = executeNativeTurn;

function _pr100SupportRejectWriteBearingMessage(message, code) {
  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error(code);
  }
}

function _pr100RequiredActionSurfaceExpression() {
  return `(() => {
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };
    const norm = (value) => String(value || '').toLowerCase().replace(/\\s+/g, ' ').trim();
    const label = (element) => norm(
      element?.getAttribute?.('aria-label') || element?.innerText || element?.textContent || ''
    );
    const controls = Array.from(document.querySelectorAll('button,[role="button"]'))
      .filter(visible)
      .slice(-256);
    const isConnect = (value) =>
      value === 'connect' || value.startsWith('connect ') ||
      value === 'подключить' || value.startsWith('подключить ');
    const isDismiss = (value) =>
      value === 'not now' || value === 'не сейчас' || value === 'cancel' || value === 'отмена';
    const providers = [
      ['gmail', ['gmail']],
      ['google_drive', ['google drive', 'гугл диск']],
      ['github', ['github']],
      ['slack', ['slack']],
      ['notion', ['notion']],
      ['outlook', ['outlook']],
      ['dropbox', ['dropbox']],
      ['onedrive', ['onedrive', 'one drive']],
      ['sharepoint', ['sharepoint']]
    ];
    const identityAttributeWhitelist = [
      'data-action-id',
      'data-required-action-id',
      'data-connector-action-id',
      'data-connect-action-id',
      'data-connector-id',
      'data-app-id',
      'data-plugin-id',
      'data-testid'
    ];
    const actionIdAttributeNames = new Set([
      'data-action-id',
      'data-required-action-id',
      'data-connector-action-id',
      'data-connect-action-id'
    ]);
    const presentIdentityAttributeNames = (root, connectControl, dismissControl) => {
      const names = new Set();
      const elements = [root, connectControl, dismissControl];
      const selector = identityAttributeWhitelist.map((name) => '[' + name + ']').join(',');
      if (root instanceof Element && selector) {
        elements.push(...Array.from(root.querySelectorAll(selector)).slice(0, 256));
      }
      for (const element of elements) {
        if (!(element instanceof Element)) continue;
        for (const name of identityAttributeWhitelist) {
          if (element.hasAttribute(name)) names.add(name);
        }
      }
      return Array.from(names).sort();
    };

    for (const connectControl of controls) {
      if (!isConnect(label(connectControl))) continue;
      let root = connectControl;
      for (let depth = 0; depth < 8 && root; depth += 1, root = root.parentElement) {
        const rootText = norm(root.innerText || root.textContent || '');
        if (!rootText || rootText.length > 12000) continue;
        const provider = providers.find(([, needles]) => needles.some((needle) => rootText.includes(needle)))?.[0] || null;
        if (!provider) continue;
        const scopedControls = Array.from(root.querySelectorAll('button,[role="button"]')).filter(visible);
        const dismissControl = scopedControls.find((element) => isDismiss(label(element))) || null;
        if (!dismissControl) continue;
        const identityAttributeNames = presentIdentityAttributeNames(
          root,
          connectControl,
          dismissControl
        );
        const stableActionIdCandidateField =
          identityAttributeNames.find((name) => actionIdAttributeNames.has(name)) || null;
        return {
          surfaceObserved: true,
          connectorName: provider,
          actionType: 'connector_authorization_required',
          connectControlPresent: true,
          dismissControlPresent: true,
          stableActionIdPresent: false,
          identityAttributeNames,
          stableActionIdCandidateField
        };
      }
    }

    return {
      surfaceObserved: false,
      connectorName: null,
      actionType: null,
      connectControlPresent: false,
      dismissControlPresent: false,
      stableActionIdPresent: false,
      identityAttributeNames: [],
      stableActionIdCandidateField: null
    };
  })()`;
}

async function _pr100CharacterizeRequiredActionSurface() {
  const runtimeTabId = await storedRuntimeTabId();
  if (!Number.isInteger(runtimeTabId)) {
    return {
      surfaceObserved: false,
      connectorName: null,
      actionType: null,
      connectControlPresent: false,
      dismissControlPresent: false,
      stableActionIdPresent: false,
      identityAttributeNames: [],
      stableActionIdCandidateField: null,
      rawDomExported: false,
      rawIdentityAttributeValuesExported: false,
      clickPerformed: false,
      writePerformed: false,
      approvalAuthorityGranted: false,
      runtimeTabPresent: false,
      debuggerAttachedAfter: null
    };
  }

  const tab = await chrome.tabs.get(runtimeTabId);
  if (!isChatGPTUrl(tab?.url || '')) {
    throw new Error('PR10_0_REQUIRED_ACTION_SURFACE_RUNTIME_TAB_NOT_CHATGPT');
  }

  const debuggee = { tabId: runtimeTabId };
  let attached = false;
  let snapshot = null;
  let debuggerAttachedAfter = null;
  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await chrome.debugger.sendCommand(debuggee, 'Runtime.enable');
    const result = await chrome.debugger.sendCommand(debuggee, 'Runtime.evaluate', {
      expression: _pr100RequiredActionSurfaceExpression(),
      returnByValue: true,
      awaitPromise: true
    });
    const value = result?.result?.value;
    if (!value || typeof value !== 'object') {
      throw new Error('PR10_0_REQUIRED_ACTION_SURFACE_RESULT_MISSING');
    }
    const identityAttributeWhitelist = new Set([
      'data-action-id',
      'data-required-action-id',
      'data-connector-action-id',
      'data-connect-action-id',
      'data-connector-id',
      'data-app-id',
      'data-plugin-id',
      'data-testid'
    ]);
    const actionIdAttributeNames = new Set([
      'data-action-id',
      'data-required-action-id',
      'data-connector-action-id',
      'data-connect-action-id'
    ]);
    const identityAttributeNames = Array.isArray(value.identityAttributeNames)
      ? value.identityAttributeNames
          .filter((name) => typeof name === 'string' && identityAttributeWhitelist.has(name))
          .slice(0, identityAttributeWhitelist.size)
      : [];
    const stableActionIdCandidateField =
      typeof value.stableActionIdCandidateField === 'string' &&
      actionIdAttributeNames.has(value.stableActionIdCandidateField)
        ? value.stableActionIdCandidateField
        : null;
    snapshot = {
      surfaceObserved: value.surfaceObserved === true,
      connectorName: typeof value.connectorName === 'string' ? value.connectorName : null,
      actionType: typeof value.actionType === 'string' ? value.actionType : null,
      connectControlPresent: value.connectControlPresent === true,
      dismissControlPresent: value.dismissControlPresent === true,
      stableActionIdPresent: false,
      identityAttributeNames,
      stableActionIdCandidateField
    };
  } finally {
    if (attached) {
      try { await chrome.debugger.detach(debuggee); } catch {}
    }
    try {
      const targets = await chrome.debugger.getTargets();
      debuggerAttachedAfter = Boolean(
        targets.find((target) => target.tabId === runtimeTabId)?.attached
      );
    } catch {
      debuggerAttachedAfter = null;
    }
  }

  if (!snapshot) {
    throw new Error('PR10_0_REQUIRED_ACTION_SURFACE_NO_SNAPSHOT');
  }
  return {
    ...snapshot,
    rawDomExported: false,
    rawIdentityAttributeValuesExported: false,
    clickPerformed: false,
    writePerformed: false,
    approvalAuthorityGranted: false,
    runtimeTabPresent: true,
    debuggerAttachedAfter
  };
}

executeNativeTurn = async function _pr100ExecuteNativeTurnWithOutermostSupportProbe(message) {
  if (message?.characterizeConnectorObservationSupport === true) {
    _pr100SupportRejectWriteBearingMessage(
      message,
      'PR10_0_CONNECTOR_SUPPORT_PROBE_MUST_BE_NO_WRITE'
    );
    return {
      connectorObservationSupported: true,
      connectorObservationSchemaVersion: PR100_CONNECTOR_OBSERVATION_SCHEMA,
      explicitConnectorIdentityRequired: true,
      explicitLifecycleCorrelationRequired: true,
      genericToolActivityImpliesConnector: false,
      rawConnectorPayloadExported: false,
      connectorObservationGrantsApprovalAuthority: false,
      connectorObservationChangesCanonicalFinality: false,
      connectorObservationChangesRetryAuthority: false,
      automaticWriteRetry: false,
      fallbackTransport: null,
      writePerformed: false
    };
  }

  if (message?.characterizeRequiredActionSurface === true) {
    _pr100SupportRejectWriteBearingMessage(
      message,
      'PR10_0_REQUIRED_ACTION_SURFACE_PROBE_MUST_BE_NO_WRITE'
    );
    return _pr100CharacterizeRequiredActionSurface();
  }

  return _pr100SupportPriorExecuteNativeTurn(message);
};
