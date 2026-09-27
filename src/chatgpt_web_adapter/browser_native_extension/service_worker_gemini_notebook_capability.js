const CWA_GEMINI_NOTEBOOK_PRODUCT_ID = "gemini-notebook-web";
const CWA_GEMINI_NOTEBOOK_ORIGINS = new Set([
  "https://notebook.google.com",
  "https://notebooklm.google.com"
]);

const CWA_GEMINI_NOTEBOOK_ADD_URL_SOURCE_OPERATION =
  "gemini_notebook_add_url_source";
const CWA_GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID = "add_url_source";
const CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CAPABILITY_ID =
  "generate_audio_overview";
const CWA_GEMINI_NOTEBOOK_GENERATE_AUDIO_OVERVIEW_OPERATION =
  "gemini_notebook_generate_audio_overview";
const CWA_GEMINI_NOTEBOOK_OBSERVE_AUDIO_OVERVIEW_OPERATION =
  "gemini_notebook_observe_audio_overview";
const CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_OPERATION =
  "gemini_notebook_audio_artifact_action_probe";
const CWA_GEMINI_NOTEBOOK_AUDIO_ACCEPTED_EVIDENCE =
  "PAGE_DOM_BACKGROUND_ARTIFACT_ACCEPTED";
const CWA_GEMINI_NOTEBOOK_AUDIO_PENDING_EVIDENCE =
  "PAGE_DOM_BACKGROUND_ARTIFACT_PENDING";
const CWA_GEMINI_NOTEBOOK_AUDIO_COMPLETION_FINALITY =
  "PAGE_DOM_DURABLE_BACKGROUND_ARTIFACT_COMPLETION";
const CWA_GEMINI_NOTEBOOK_AUDIO_OBSERVATION_STABLE_MS = 1000;
const CWA_GEMINI_NOTEBOOK_FINALITY =
  "PAGE_DOM_DURABLE_SOURCE_ADMISSION";
const CWA_GEMINI_NOTEBOOK_SOURCE_ROW_STABLE_MS = 1200;

function _cwaGeminiNotebookCanonicalNotebookUrl(value) {
  try {
    const parsed = new URL(value);
    if (!CWA_GEMINI_NOTEBOOK_ORIGINS.has(parsed.origin)) return null;
    if (!/^\/notebook\/[A-Za-z0-9_-]{8,200}\/?$/.test(parsed.pathname)) {
      return null;
    }
    return parsed.origin + parsed.pathname.replace(/\/$/, "");
  } catch {
    return null;
  }
}

function _cwaGeminiNotebookSourceUrl(value) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error("GEMINI_NOTEBOOK_SOURCE_URL_REQUIRED");
  }
  if (value.length > 2048) {
    throw new Error("GEMINI_NOTEBOOK_SOURCE_URL_TOO_LARGE");
  }
  let parsed;
  try {
    parsed = new URL(value.trim());
  } catch {
    throw new Error("GEMINI_NOTEBOOK_SOURCE_URL_INVALID");
  }
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("GEMINI_NOTEBOOK_SOURCE_URL_SCHEME_UNSUPPORTED");
  }
  if (!parsed.hostname || parsed.username || parsed.password) {
    throw new Error("GEMINI_NOTEBOOK_SOURCE_URL_INVALID");
  }
  return parsed.toString();
}

async function _cwaGeminiNotebookFindExactOpenTab(notebookUrl) {
  const tabs = (
    await chrome.tabs.query({
      url: [
        "https://notebook.google.com/*",
        "https://notebooklm.google.com/*"
      ]
    })
  ).filter(
    (tab) =>
      Number.isInteger(tab?.id) &&
      _cwaGeminiNotebookCanonicalNotebookUrl(tab?.url || "") === notebookUrl
  );

  if (tabs.length === 0) {
    throw new Error("GEMINI_NOTEBOOK_TARGET_TAB_MISSING");
  }
  if (tabs.length > 1) {
    throw new Error(
      "GEMINI_NOTEBOOK_TARGET_TAB_AMBIGUOUS:" + String(tabs.length)
    );
  }
  return tabs[0];
}

async function _cwaGeminiNotebookMutationEvaluate(debuggee, expression) {
  const result = await _cwaBaseSendCommand(debuggee, "Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true
  });
  if (result?.exceptionDetails) {
    throw new Error("GEMINI_NOTEBOOK_PAGE_EVALUATION_FAILED");
  }
  return result?.result?.value;
}

function _cwaGeminiNotebookSourceRowsExpression() {
  return `(() => {
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      );
    };
    const normalize = (value) =>
      String(value || "").replace(/\\s+/g, " ").trim();
    const notebookUrl =
      location.origin + location.pathname.replace(/\\/$/, "");
    const panel = document.querySelector("section.source-panel");
    const picker = panel?.querySelector("source-picker") || null;
    const rows = [];
    if (picker instanceof Element) {
      for (const row of picker.querySelectorAll(".single-source-container")) {
        if (rows.length >= 100) break;
        if (!visible(row)) continue;
        const titleElement =
          row.querySelector(".source-title") ||
          row.querySelector(".source-stretched-button");
        const stretchedButton = row.querySelector(".source-stretched-button");
        const checkbox = row.querySelector("input[type='checkbox']");
        const moreButton = row.querySelector(
          "[id^='source-item-more-button-']"
        );
        const moreButtonId = String(moreButton?.id || "");
        const prefix = "source-item-more-button-";
        const observedRowRef = moreButtonId.startsWith(prefix)
          ? moreButtonId.slice(prefix.length)
          : null;
        const title = normalize(
          titleElement?.getAttribute("aria-label") ||
            titleElement?.innerText ||
            titleElement?.textContent ||
            stretchedButton?.getAttribute("aria-label") ||
            ""
        );
        rows.push({
          title: title.slice(0, 220),
          selected:
            checkbox && "checked" in checkbox
              ? Boolean(checkbox.checked)
              : null,
          observedRowRef
        });
      }
    }
    return {
      notebookUrl,
      sourcePanelFound: panel instanceof Element,
      sourcePickerFound: picker instanceof Element,
      rows
    };
  })()`;
}



function _cwaGeminiNotebookAudioArtifactItemsExpression() {
  return `(() => {
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 &&
        style.display !== "none" && style.visibility !== "hidden";
    };
    const normalize = (value) =>
      String(value || "").replace(/\\s+/g, " ").trim();
    const clip = (value, limit = 180) => normalize(value).slice(0, limit);
    const classText = (element) =>
      clip(
        typeof element?.className === "string"
          ? element.className
          : element?.getAttribute?.("class") || "",
        180
      );
    const iconTexts = (element) =>
      Array.from(element?.querySelectorAll?.("mat-icon") || [])
        .slice(0, 8)
        .map((icon) => clip(icon.textContent, 48))
        .filter(Boolean);

    const notebookUrl =
      location.origin + location.pathname.replace(/\\/$/, "");
    const studio = document.querySelector("section.studio-panel");
    const container =
      studio?.querySelector(".artifact-library-container") || null;
    const library = container?.querySelector("artifact-library") || null;
    const rows = [];

    if (library instanceof Element) {
      for (const row of library.querySelectorAll(".artifact-item-button")) {
        if (rows.length >= 20) break;
        if (!visible(row)) continue;

        const labels = row.querySelector("[id^='artifact-labels-']");
        const labelsId = String(labels?.id || "");
        const prefix = "artifact-labels-";
        const observedArtifactRef = labelsId.startsWith(prefix)
          ? labelsId.slice(prefix.length)
          : null;
        const actionButton =
          row.querySelector("button.artifact-stretched-button") ||
          row.querySelector("button") ||
          null;
        const icons = iconTexts(row);
        const actionDisabled =
          actionButton instanceof Element
            ? Boolean(actionButton.disabled) ||
              actionButton.getAttribute("aria-disabled") === "true" ||
              actionButton.classList.contains("mat-mdc-button-disabled")
            : null;
        const pendingIcon = icons.includes("progress_activity");
        let statusCandidate = "UNKNOWN";
        if (observedArtifactRef && pendingIcon && actionDisabled === true) {
          statusCandidate = "PENDING_CANDIDATE";
        } else if (
          observedArtifactRef &&
          !pendingIcon &&
          actionButton instanceof Element &&
          actionDisabled === false
        ) {
          statusCandidate = "NON_PENDING_CANDIDATE";
        }

        rows.push({
          observedArtifactRef,
          rowClassName: classText(row),
          title: clip(row.querySelector(".artifact-title")?.textContent || ""),
          details: clip(row.querySelector(".artifact-details")?.textContent || ""),
          icons,
          actionButtonFound: actionButton instanceof Element,
          actionDisabled,
          statusCandidate
        });
      }
    }

    return {
      notebookUrl,
      studioFound: studio instanceof Element && visible(studio),
      containerFound: container instanceof Element && visible(container),
      libraryFound: library instanceof Element && visible(library),
      emptyMarker:
        container instanceof Element &&
        container.classList.contains("artifact-library-container-empty"),
      rows
    };
  })()`;
}


function _cwaGeminiNotebookAudioArtifactActionProbeExpression(
  expectedArtifactRef
) {
  const encodedArtifactRef = JSON.stringify(expectedArtifactRef);
  return `(() => {
    const expectedArtifactRef = \${encodedArtifactRef};
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      );
    };
    const normalize = (value) =>
      String(value || "").replace(/\\s+/g, " ").trim();
    const clip = (value, limit = 160) => normalize(value).slice(0, limit);
    const classText = (element) =>
      clip(
        typeof element?.className === "string"
          ? element.className
          : element?.getAttribute?.("class") || "",
        180
      );
    const iconTexts = (element) =>
      Array.from(element?.querySelectorAll?.("mat-icon") || [])
        .slice(0, 8)
        .map((icon) => clip(icon.textContent, 48))
        .filter(Boolean);
    const ancestorPath = (element, row) => {
      const path = [];
      let current = element?.parentElement || null;
      while (
        current instanceof Element &&
        current !== row &&
        path.length < 4
      ) {
        path.push({
          tag: String(current.tagName || "").toLowerCase(),
          id: clip(current.id || "", 120),
          className: classText(current),
          role: clip(current.getAttribute("role") || "", 48)
        });
        current = current.parentElement;
      }
      return path;
    };

    const notebookUrl =
      location.origin + location.pathname.replace(/\\/$/, "");
    const studio = document.querySelector("section.studio-panel");
    const library =
      studio?.querySelector(".artifact-library-container artifact-library") ||
      null;
    const matches = [];

    if (library instanceof Element) {
      for (const row of library.querySelectorAll(".artifact-item-button")) {
        if (!visible(row)) continue;
        const labels = row.querySelector("[id^='artifact-labels-']");
        const labelsId = String(labels?.id || "");
        const prefix = "artifact-labels-";
        const observedArtifactRef = labelsId.startsWith(prefix)
          ? labelsId.slice(prefix.length)
          : null;
        if (observedArtifactRef === expectedArtifactRef) {
          matches.push({ row, labelsId });
        }
      }
    }

    if (matches.length !== 1) {
      return {
        notebookUrl,
        studioFound: studio instanceof Element && visible(studio),
        libraryFound: library instanceof Element && visible(library),
        rowIdentityResolved: false,
        matchCount: matches.length,
        row: null,
        controls: [],
        moreVertCandidates: []
      };
    }

    const { row, labelsId } = matches[0];
    const controls = Array.from(
      row.querySelectorAll("button,[role='button']")
    )
      .filter(visible)
      .slice(0, 16)
      .map((control, index) => ({
        index,
        tag: String(control.tagName || "").toLowerCase(),
        id: clip(control.id || "", 120),
        className: classText(control),
        role: clip(control.getAttribute("role") || "", 48),
        ariaLabel: clip(control.getAttribute("aria-label") || "", 160),
        title: clip(control.getAttribute("title") || "", 160),
        disabled:
          "disabled" in control
            ? Boolean(control.disabled)
            : control.getAttribute("aria-disabled") === "true",
        icons: iconTexts(control),
        ancestors: ancestorPath(control, row)
      }));

    const moreVertCandidates = controls.filter((control) =>
      Array.isArray(control.icons) && control.icons.includes("more_vert")
    );

    return {
      notebookUrl,
      studioFound: studio instanceof Element && visible(studio),
      libraryFound: library instanceof Element && visible(library),
      rowIdentityResolved: true,
      matchCount: 1,
      row: {
        observedArtifactRef: expectedArtifactRef,
        labelsId,
        className: classText(row),
        icons: iconTexts(row),
        controlCount: controls.length
      },
      controls,
      moreVertCandidates
    };
  })()`;
}

async function _cwaGeminiNotebookProbeAudioArtifactAction(message) {
  if (message?.productId !== CWA_GEMINI_NOTEBOOK_PRODUCT_ID) {
    throw new Error("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH");
  }

  const notebookUrl = _cwaGeminiNotebookCanonicalNotebookUrl(
    message?.notebookUrl
  );
  if (!notebookUrl) {
    throw new Error("GEMINI_NOTEBOOK_NOTEBOOK_URL_INVALID");
  }

  const expectedArtifactRef =
    typeof message?.expectedArtifactRef === "string" &&
    /^[A-Za-z0-9_-]{8,200}$/.test(message.expectedArtifactRef)
      ? message.expectedArtifactRef
      : null;
  if (!expectedArtifactRef) {
    throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_INVALID");
  }

  const startedAt = performance.now();
  const tab = await _cwaGeminiNotebookFindExactOpenTab(notebookUrl);
  const debuggee = { tabId: tab.id };
  let attached = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const state = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookAudioArtifactActionProbeExpression(
        expectedArtifactRef
      )
    );
    if (state?.notebookUrl !== notebookUrl) {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_NOTEBOOK_ROUTE_CHANGED");
    }
    if (
      state?.studioFound !== true ||
      state?.libraryFound !== true ||
      state?.rowIdentityResolved !== true ||
      state?.matchCount !== 1
    ) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_ROW_IDENTITY_UNRESOLVED"
      );
    }
    if (state?.row?.observedArtifactRef !== expectedArtifactRef) {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_MISMATCH");
    }

    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      notebookUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      observedArtifactRef: expectedArtifactRef,
      row: state.row,
      controls: Array.isArray(state.controls) ? state.controls : [],
      moreVertCandidates: Array.isArray(state.moreVertCandidates)
        ? state.moreVertCandidates
        : [],
      rawDomExported: false,
      writePerformed: false,
      navigationPerformed: false,
      downloadPerformed: false
    };
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Read-only row characterization cannot change product state.
      }
    }
  }
}

function _cwaGeminiNotebookAudioConfigReadinessExpression() {
  return `(() => {
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 &&
        style.display !== "none" && style.visibility !== "hidden";
    };
    const dialogs = Array.from(
      document.querySelectorAll(
        "mat-dialog-container[role='dialog'],[role='dialog']"
      )
    ).filter(visible);
    if (dialogs.length !== 1) return { ready: false };

    const dialog = dialogs[0];
    const icons = Array.from(dialog.querySelectorAll("mat-icon")).map(
      (icon) => String(icon.textContent || "").trim()
    );
    if (!icons.includes("audio_magic_eraser")) return { ready: false };

    const actions =
      dialog.querySelector(".mat-mdc-dialog-actions") ||
      dialog.querySelector("[class*='dialog-actions']") ||
      null;
    if (!(actions instanceof Element)) return { ready: false };

    const actualButtons = Array.from(actions.querySelectorAll("button")).filter(
      visible
    );
    const tonalCandidates = actualButtons.filter(
      (button) =>
        button.classList.contains("mat-tonal-button") &&
        !button.disabled &&
        button.getAttribute("aria-disabled") !== "true"
    );
    return {
      ready: actualButtons.length === 2 && tonalCandidates.length === 1,
      actualButtonCount: actualButtons.length,
      tonalCandidateCount: tonalCandidates.length
    };
  })()`;
}

function _cwaGeminiNotebookClickAudioOverviewExpression() {
  return `(() => {
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 &&
        style.display !== "none" && style.visibility !== "hidden";
    };
    const studio = document.querySelector("section.studio-panel");
    if (!(studio instanceof Element) || !visible(studio)) {
      return { clicked: false, reason: "STUDIO_OWNER_MISSING" };
    }
    const candidates = Array.from(
      studio.querySelectorAll("basic-create-artifact-button")
    )
      .map((owner) => {
        const control =
          owner.querySelector("[role='button']") ||
          owner.querySelector("button") ||
          null;
        const icons =
          control instanceof Element
            ? Array.from(control.querySelectorAll("mat-icon")).map(
                (icon) => String(icon.textContent || "").trim()
              )
            : [];
        return { control, icons };
      })
      .filter(
        (entry) =>
          entry.control instanceof Element &&
          visible(entry.control) &&
          entry.icons.includes("audio_spark")
      );
    if (candidates.length !== 1) {
      return {
        clicked: false,
        reason: "AUDIO_CREATE_CONTROL_IDENTITY_UNRESOLVED",
        candidateCount: candidates.length
      };
    }
    const control = candidates[0].control;
    if (
      control.getAttribute("aria-disabled") === "true" ||
      ("disabled" in control && Boolean(control.disabled))
    ) {
      return { clicked: false, reason: "AUDIO_CREATE_CONTROL_DISABLED" };
    }
    control.click();
    return { clicked: true };
  })()`;
}

function _cwaGeminiNotebookClickAudioGenerateNowExpression() {
  return `(() => {
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 &&
        style.display !== "none" && style.visibility !== "hidden";
    };
    const dialogs = Array.from(
      document.querySelectorAll(
        "mat-dialog-container[role='dialog'],[role='dialog']"
      )
    ).filter(visible);
    if (dialogs.length !== 1) {
      return { clicked: false, reason: "AUDIO_CONFIG_DIALOG_IDENTITY_UNRESOLVED" };
    }
    const dialog = dialogs[0];
    const icons = Array.from(dialog.querySelectorAll("mat-icon")).map(
      (icon) => String(icon.textContent || "").trim()
    );
    if (!icons.includes("audio_magic_eraser")) {
      return { clicked: false, reason: "AUDIO_CONFIG_DIALOG_OWNER_UNRESOLVED" };
    }
    const actions =
      dialog.querySelector(".mat-mdc-dialog-actions") ||
      dialog.querySelector("[class*='dialog-actions']") ||
      null;
    if (!(actions instanceof Element)) {
      return { clicked: false, reason: "AUDIO_CONFIG_ACTIONS_MISSING" };
    }
    const actualButtons = Array.from(actions.querySelectorAll("button")).filter(
      visible
    );
    const tonalCandidates = actualButtons.filter(
      (button) =>
        button.classList.contains("mat-tonal-button") &&
        !button.disabled &&
        button.getAttribute("aria-disabled") !== "true"
    );
    if (actualButtons.length !== 2 || tonalCandidates.length !== 1) {
      return {
        clicked: false,
        reason: "AUDIO_GENERATE_NOW_IDENTITY_UNRESOLVED",
        actionButtonCount: actualButtons.length,
        tonalCandidateCount: tonalCandidates.length
      };
    }
    tonalCandidates[0].click();
    return { clicked: true };
  })()`;
}

async function _cwaGeminiNotebookWaitForAudioConfig(debuggee, deadlineAt) {
  while (performance.now() < deadlineAt) {
    const state = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookAudioConfigReadinessExpression()
    );
    if (state?.ready === true) return state;
    await sleep(100);
  }
  throw new Error("GEMINI_NOTEBOOK_AUDIO_CONFIG_TIMEOUT");
}

async function _cwaGeminiNotebookWaitForStableAudioArtifact(
  debuggee,
  notebookUrl,
  expectedArtifactRef,
  deadlineAt
) {
  let stableSignature = null;
  let stableSince = null;
  let lastRows = -1;

  while (performance.now() < deadlineAt) {
    const state = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookAudioArtifactItemsExpression()
    );
    if (state?.notebookUrl !== notebookUrl) {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_NOTEBOOK_ROUTE_CHANGED");
    }
    if (
      state?.studioFound !== true ||
      state?.containerFound !== true ||
      state?.libraryFound !== true
    ) {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_LIBRARY_NOT_READY");
    }

    const rows = Array.isArray(state?.rows) ? state.rows : [];
    lastRows = rows.length;
    if (rows.length > 1) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_IDENTITY_UNRESOLVED:" +
          String(rows.length)
      );
    }
    if (rows.length === 0) {
      stableSignature = null;
      stableSince = null;
      await sleep(200);
      continue;
    }

    const row = rows[0];
    if (!row?.observedArtifactRef) {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_UNRESOLVED");
    }
    if (
      expectedArtifactRef &&
      String(row.observedArtifactRef) !== expectedArtifactRef
    ) {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_MISMATCH");
    }
    if (
      row.statusCandidate !== "PENDING_CANDIDATE" &&
      row.statusCandidate !== "NON_PENDING_CANDIDATE"
    ) {
      stableSignature = null;
      stableSince = null;
      await sleep(200);
      continue;
    }

    const signature = JSON.stringify({
      observedArtifactRef: row.observedArtifactRef,
      statusCandidate: row.statusCandidate,
      actionDisabled: row.actionDisabled,
      icons: row.icons
    });
    if (signature !== stableSignature) {
      stableSignature = signature;
      stableSince = performance.now();
    } else if (
      stableSince !== null &&
      performance.now() - stableSince >=
        CWA_GEMINI_NOTEBOOK_AUDIO_OBSERVATION_STABLE_MS
    ) {
      return { state, row };
    }
    await sleep(200);
  }

  throw new Error(
    "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_STABLE_TIMEOUT:rows=" + String(lastRows)
  );
}

async function _cwaGeminiNotebookReloadExactNotebookTab(
  tabId,
  notebookUrl,
  timeoutMs
) {
  return new Promise((resolve, reject) => {
    let settled = false;
    let sawLoading = false;
    const timer = setTimeout(
      () => finish(new Error("GEMINI_NOTEBOOK_RELOAD_TIMEOUT")),
      timeoutMs
    );

    function cleanup() {
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(onUpdated);
    }

    async function finish(error = null) {
      if (settled) return;
      settled = true;
      cleanup();
      if (error) {
        reject(error);
        return;
      }
      try {
        const tab = await chrome.tabs.get(tabId);
        if (
          _cwaGeminiNotebookCanonicalNotebookUrl(tab?.url || "") !== notebookUrl
        ) {
          reject(new Error("GEMINI_NOTEBOOK_RELOAD_ROUTE_MISMATCH"));
          return;
        }
        resolve(tab);
      } catch (caught) {
        reject(caught);
      }
    }

    function onUpdated(updatedTabId, changeInfo) {
      if (updatedTabId !== tabId) return;
      if (changeInfo.status === "loading") {
        sawLoading = true;
      } else if (changeInfo.status === "complete" && sawLoading) {
        void finish();
      }
    }

    chrome.tabs.onUpdated.addListener(onUpdated);
    chrome.tabs.reload(tabId).catch((error) => void finish(error));
  });
}

async function _cwaGeminiNotebookGenerateAudioOverview(message) {
  if (message?.productId !== CWA_GEMINI_NOTEBOOK_PRODUCT_ID) {
    throw new Error("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH");
  }
  if (
    message?.capabilityId !== CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CAPABILITY_ID
  ) {
    throw new Error("GEMINI_NOTEBOOK_CAPABILITY_ID_MISMATCH");
  }

  const notebookUrl = _cwaGeminiNotebookCanonicalNotebookUrl(
    message?.notebookUrl
  );
  if (!notebookUrl) throw new Error("GEMINI_NOTEBOOK_NOTEBOOK_URL_INVALID");

  const timeoutMs = Math.max(
    5000,
    Math.min(Number(message?.timeoutMs) || 60000, 120000)
  );
  const startedAt = performance.now();
  const deadlineAt = startedAt + timeoutMs;
  const tab = await _cwaGeminiNotebookFindExactOpenTab(notebookUrl);
  const debuggee = { tabId: tab.id };
  let attached = false;
  let generationCommitMayHaveExecuted = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const before = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookAudioArtifactItemsExpression()
    );
    const beforeRows = Array.isArray(before?.rows) ? before.rows : [];
    if (
      before?.notebookUrl !== notebookUrl ||
      before?.studioFound !== true ||
      before?.containerFound !== true ||
      before?.libraryFound !== true ||
      before?.emptyMarker !== true ||
      beforeRows.length !== 0
    ) {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_PRESTATE_NOT_EMPTY");
    }

    const opened = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookClickAudioOverviewExpression()
    );
    if (opened?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_CONFIG_OPEN_FAILED:" +
          String(opened?.reason || "UNKNOWN")
      );
    }

    await _cwaGeminiNotebookWaitForAudioConfig(debuggee, deadlineAt);

    generationCommitMayHaveExecuted = true;
    const committed = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookClickAudioGenerateNowExpression()
    );
    if (committed?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_GENERATE_CLICK_FAILED:" +
          String(committed?.reason || "UNKNOWN")
      );
    }

    const accepted = await _cwaGeminiNotebookWaitForStableAudioArtifact(
      debuggee,
      notebookUrl,
      null,
      deadlineAt
    );
    const row = accepted.row;
    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      capabilityId: CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CAPABILITY_ID,
      notebookUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      generationCommitMayHaveExecuted: true,
      generationAcceptedProven: true,
      observedArtifactRef: String(row.observedArtifactRef),
      artifactStatus:
        row.statusCandidate === "PENDING_CANDIDATE"
          ? "PENDING"
          : "COMPLETION_CANDIDATE",
      artifactTitle: String(row.title || ""),
      artifactDetails: String(row.details || ""),
      startEvidence: CWA_GEMINI_NOTEBOOK_AUDIO_ACCEPTED_EVIDENCE,
      canonicalCompletionProven: false,
      automaticRetry: false
    };
  } catch (error) {
    if (generationCommitMayHaveExecuted) {
      throw _cwaGeminiNotebookAmbiguousError(error);
    }
    throw error;
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {}
    }
  }
}

async function _cwaGeminiNotebookObserveAudioOverview(message) {
  if (message?.productId !== CWA_GEMINI_NOTEBOOK_PRODUCT_ID) {
    throw new Error("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH");
  }
  if (
    message?.capabilityId !== CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CAPABILITY_ID
  ) {
    throw new Error("GEMINI_NOTEBOOK_CAPABILITY_ID_MISMATCH");
  }

  const notebookUrl = _cwaGeminiNotebookCanonicalNotebookUrl(
    message?.notebookUrl
  );
  if (!notebookUrl) throw new Error("GEMINI_NOTEBOOK_NOTEBOOK_URL_INVALID");

  const observedArtifactRef =
    typeof message?.observedArtifactRef === "string" &&
    /^[A-Za-z0-9_-]{8,200}$/.test(message.observedArtifactRef)
      ? message.observedArtifactRef
      : null;
  if (!observedArtifactRef) {
    throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_REF_INVALID");
  }

  const timeoutMs = Math.max(
    5000,
    Math.min(Number(message?.timeoutMs) || 60000, 120000)
  );
  const startedAt = performance.now();
  const deadlineAt = startedAt + timeoutMs;
  const tab = await _cwaGeminiNotebookFindExactOpenTab(notebookUrl);
  const debuggee = { tabId: tab.id };
  let attached = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const beforeReload = await _cwaGeminiNotebookWaitForStableAudioArtifact(
      debuggee,
      notebookUrl,
      observedArtifactRef,
      deadlineAt
    );
    const firstRow = beforeReload.row;

    if (firstRow.statusCandidate === "PENDING_CANDIDATE") {
      return {
        productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
        capabilityId: CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CAPABILITY_ID,
        notebookUrl,
        tabId: tab.id,
        elapsedMs: Math.round(performance.now() - startedAt),
        observedArtifactRef,
        artifactStatus: "PENDING",
        artifactTitle: String(firstRow.title || ""),
        artifactDetails: String(firstRow.details || ""),
        completionProven: false,
        reloadVerified: false,
        finalityEvidence: CWA_GEMINI_NOTEBOOK_AUDIO_PENDING_EVIDENCE,
        canonicalCompletionProven: false,
        automaticRetry: false,
        writePerformed: false,
        navigationPerformed: false
      };
    }

    await chrome.debugger.detach(debuggee);
    attached = false;
    const reloadBudget = Math.max(
      3000,
      Math.min(45000, deadlineAt - performance.now())
    );
    await _cwaGeminiNotebookReloadExactNotebookTab(
      tab.id,
      notebookUrl,
      reloadBudget
    );

    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const afterReload = await _cwaGeminiNotebookWaitForStableAudioArtifact(
      debuggee,
      notebookUrl,
      observedArtifactRef,
      deadlineAt
    );
    const durableRow = afterReload.row;
    if (durableRow.statusCandidate !== "NON_PENDING_CANDIDATE") {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_DURABLE_COMPLETION_NOT_CONFIRMED");
    }

    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      capabilityId: CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_CAPABILITY_ID,
      notebookUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      observedArtifactRef,
      artifactStatus: "COMPLETED",
      artifactTitle: String(durableRow.title || ""),
      artifactDetails: String(durableRow.details || ""),
      completionProven: true,
      reloadVerified: true,
      finalityEvidence: CWA_GEMINI_NOTEBOOK_AUDIO_COMPLETION_FINALITY,
      canonicalCompletionProven: false,
      automaticRetry: false,
      writePerformed: false,
      navigationPerformed: true
    };
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {}
    }
  }
}

function _cwaGeminiNotebookClickAddSourceExpression() {
  return `(() => {
    const panel = document.querySelector("section.source-panel");
    const trigger = panel?.querySelector(".add-source-button") || null;
    const button =
      trigger instanceof HTMLButtonElement
        ? trigger
        : trigger?.querySelector("button") || null;
    if (!(button instanceof HTMLButtonElement)) {
      return { clicked: false, reason: "ADD_SOURCE_CONTROL_MISSING" };
    }
    if (button.disabled || button.getAttribute("aria-disabled") === "true") {
      return { clicked: false, reason: "ADD_SOURCE_CONTROL_DISABLED" };
    }
    button.click();
    return { clicked: true };
  })()`;
}

function _cwaGeminiNotebookDialogStateExpression() {
  return `(() => {
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      );
    };
    const dialogs = Array.from(
      document.querySelectorAll(
        "mat-dialog-container[role='dialog'],[role='dialog']"
      )
    ).filter(visible);
    const dialog =
      dialogs.find(
        (candidate) =>
          !dialogs.some(
            (other) => other !== candidate && candidate.contains(other)
          )
      ) || dialogs[0] || null;
    if (!(dialog instanceof Element)) {
      return {
        dialogFound: false,
        directUrlState: false,
        sitesActionCount: 0
      };
    }

    const textareas = Array.from(dialog.querySelectorAll("textarea")).filter(
      visible
    );
    const commitButtons = Array.from(
      dialog.querySelectorAll(".mat-mdc-dialog-actions button")
    ).filter(visible);
    const sourceActionButtons = Array.from(
      dialog.querySelectorAll("button.source-action-button")
    ).filter(visible);
    const sitesActions = sourceActionButtons.filter((button) => {
      const icons = Array.from(button.querySelectorAll("mat-icon")).map(
        (icon) => String(icon.textContent || "").trim()
      );
      return icons.includes("link_2") && icons.includes("video_youtube");
    });

    return {
      dialogFound: true,
      directUrlState: textareas.length === 1 && commitButtons.length === 1,
      sitesActionCount: sitesActions.length
    };
  })()`;
}

function _cwaGeminiNotebookClickSitesExpression() {
  return `(() => {
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      );
    };
    const dialogs = Array.from(
      document.querySelectorAll(
        "mat-dialog-container[role='dialog'],[role='dialog']"
      )
    ).filter(visible);
    const dialog =
      dialogs.find(
        (candidate) =>
          !dialogs.some(
            (other) => other !== candidate && candidate.contains(other)
          )
      ) || dialogs[0] || null;
    if (!(dialog instanceof Element)) {
      return { clicked: false, reason: "SOURCE_DIALOG_MISSING" };
    }
    const candidates = Array.from(
      dialog.querySelectorAll("button.source-action-button")
    ).filter((button) => {
      if (!visible(button)) return false;
      const icons = Array.from(button.querySelectorAll("mat-icon")).map(
        (icon) => String(icon.textContent || "").trim()
      );
      return icons.includes("link_2") && icons.includes("video_youtube");
    });
    if (candidates.length !== 1) {
      return {
        clicked: false,
        reason: "SITES_ACTION_IDENTITY_UNRESOLVED",
        candidateCount: candidates.length
      };
    }
    candidates[0].click();
    return { clicked: true };
  })()`;
}

function _cwaGeminiNotebookUrlInputExpression(sourceUrl, write) {
  const encodedSourceUrl = JSON.stringify(sourceUrl);
  return `(() => {
    const requestedUrl = ${encodedSourceUrl};
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      );
    };
    const dialogs = Array.from(
      document.querySelectorAll(
        "mat-dialog-container[role='dialog'],[role='dialog']"
      )
    ).filter(visible);
    const dialog =
      dialogs.find(
        (candidate) =>
          !dialogs.some(
            (other) => other !== candidate && candidate.contains(other)
          )
      ) || dialogs[0] || null;
    if (!(dialog instanceof Element)) {
      return { identityResolved: false, reason: "SOURCE_DIALOG_MISSING" };
    }
    const textareas = Array.from(dialog.querySelectorAll("textarea")).filter(
      visible
    );
    const commitButtons = Array.from(
      dialog.querySelectorAll(".mat-mdc-dialog-actions button")
    ).filter(visible);
    if (textareas.length !== 1 || commitButtons.length !== 1) {
      return {
        identityResolved: false,
        reason: "URL_SOURCE_CONTROL_IDENTITY_UNRESOLVED",
        textareaCount: textareas.length,
        commitButtonCount: commitButtons.length
      };
    }
    const input = textareas[0];
    const commit = commitButtons[0];
    if (${write ? "true" : "false"}) {
      input.focus();
      const setter = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        "value"
      )?.set;
      if (typeof setter === "function") {
        setter.call(input, requestedUrl);
      } else {
        input.value = requestedUrl;
      }
      input.dispatchEvent(
        new InputEvent("input", {
          bubbles: true,
          inputType: "insertText",
          data: requestedUrl
        })
      );
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
    return {
      identityResolved: true,
      inputMatchesRequested: input.value === requestedUrl,
      commitDisabled:
        Boolean(commit.disabled) ||
        commit.getAttribute("aria-disabled") === "true" ||
        commit.classList.contains("mat-mdc-button-disabled")
    };
  })()`;
}

function _cwaGeminiNotebookCommitExpression(sourceUrl) {
  const encodedSourceUrl = JSON.stringify(sourceUrl);
  return `(() => {
    const requestedUrl = ${encodedSourceUrl};
    const visible = (element) => {
      if (!(element instanceof Element)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      );
    };
    const dialogs = Array.from(
      document.querySelectorAll(
        "mat-dialog-container[role='dialog'],[role='dialog']"
      )
    ).filter(visible);
    const dialog =
      dialogs.find(
        (candidate) =>
          !dialogs.some(
            (other) => other !== candidate && candidate.contains(other)
          )
      ) || dialogs[0] || null;
    if (!(dialog instanceof Element)) {
      return { clicked: false, reason: "SOURCE_DIALOG_MISSING" };
    }
    const textareas = Array.from(dialog.querySelectorAll("textarea")).filter(
      visible
    );
    const commitButtons = Array.from(
      dialog.querySelectorAll(".mat-mdc-dialog-actions button")
    ).filter(visible);
    if (textareas.length !== 1 || commitButtons.length !== 1) {
      return {
        clicked: false,
        reason: "URL_SOURCE_CONTROL_IDENTITY_UNRESOLVED"
      };
    }
    const input = textareas[0];
    const commit = commitButtons[0];
    if (input.value !== requestedUrl) {
      return { clicked: false, reason: "URL_SOURCE_INPUT_MISMATCH" };
    }
    if (
      commit.disabled ||
      commit.getAttribute("aria-disabled") === "true" ||
      commit.classList.contains("mat-mdc-button-disabled")
    ) {
      return { clicked: false, reason: "URL_SOURCE_COMMIT_DISABLED" };
    }
    commit.click();
    return { clicked: true };
  })()`;
}

function _cwaGeminiNotebookAmbiguousError(error) {
  const message = String(error?.message || error || "UNKNOWN");
  if (
    message.startsWith(
      "GEMINI_NOTEBOOK_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
    )
  ) {
    return error;
  }
  return new Error(
    "GEMINI_NOTEBOOK_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
      message
  );
}

async function _cwaGeminiNotebookWaitForDialogState(
  debuggee,
  predicate,
  deadlineAt,
  timeoutCode
) {
  while (performance.now() < deadlineAt) {
    const state = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookDialogStateExpression()
    );
    if (predicate(state)) return state;
    await sleep(100);
  }
  throw new Error(timeoutCode);
}

async function _cwaGeminiNotebookWaitForCommitEnabled(
  debuggee,
  sourceUrl,
  deadlineAt
) {
  while (performance.now() < deadlineAt) {
    const state = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookUrlInputExpression(sourceUrl, false)
    );
    if (
      state?.identityResolved === true &&
      state?.inputMatchesRequested === true &&
      state?.commitDisabled === false
    ) {
      return state;
    }
    await sleep(100);
  }
  throw new Error("GEMINI_NOTEBOOK_PRECOMMIT_ENABLE_TIMEOUT");
}

async function _cwaGeminiNotebookWaitForDurableSourceRow(
  debuggee,
  notebookUrl,
  preRefs,
  deadlineAt
) {
  let stableRef = null;
  let stableSince = null;
  let lastSnapshot = null;

  while (performance.now() < deadlineAt) {
    const snapshot = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookSourceRowsExpression()
    );
    lastSnapshot = snapshot;
    if (snapshot?.notebookUrl !== notebookUrl) {
      throw new Error(
        "GEMINI_NOTEBOOK_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
          "NOTEBOOK_ROUTE_CHANGED"
      );
    }
    const rows = Array.isArray(snapshot?.rows) ? snapshot.rows : [];
    if (rows.some((row) => !row?.observedRowRef)) {
      throw new Error(
        "GEMINI_NOTEBOOK_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
          "POSTCOMMIT_ROW_IDENTITY_UNRESOLVED"
      );
    }
    const newRows = rows.filter(
      (row) => !preRefs.has(String(row.observedRowRef))
    );
    if (newRows.length > 1) {
      throw new Error(
        "GEMINI_NOTEBOOK_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
          "MULTIPLE_NEW_SOURCE_ROWS"
      );
    }
    if (newRows.length === 1 && String(newRows[0]?.title || "").trim()) {
      const candidateRef = String(newRows[0].observedRowRef);
      if (candidateRef !== stableRef) {
        stableRef = candidateRef;
        stableSince = performance.now();
      } else if (
        stableSince !== null &&
        performance.now() - stableSince >=
          CWA_GEMINI_NOTEBOOK_SOURCE_ROW_STABLE_MS
      ) {
        return {
          row: newRows[0],
          rowCount: rows.length
        };
      }
    } else {
      stableRef = null;
      stableSince = null;
    }
    await sleep(200);
  }

  const observedCount = Array.isArray(lastSnapshot?.rows)
    ? lastSnapshot.rows.length
    : -1;
  throw new Error(
    "GEMINI_NOTEBOOK_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:" +
      "DURABLE_SOURCE_ROW_TIMEOUT:rows=" +
      String(observedCount)
  );
}

async function _cwaGeminiNotebookAddUrlSource(message) {
  if (message?.productId !== CWA_GEMINI_NOTEBOOK_PRODUCT_ID) {
    throw new Error("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH");
  }
  if (
    message?.capabilityId !==
    CWA_GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID
  ) {
    throw new Error("GEMINI_NOTEBOOK_CAPABILITY_ID_MISMATCH");
  }

  const notebookUrl = _cwaGeminiNotebookCanonicalNotebookUrl(
    message?.notebookUrl
  );
  if (!notebookUrl) {
    throw new Error("GEMINI_NOTEBOOK_NOTEBOOK_URL_INVALID");
  }
  const sourceUrl = _cwaGeminiNotebookSourceUrl(message?.sourceUrl);
  const timeoutMs = Math.max(
    5000,
    Math.min(Number(message?.timeoutMs) || 60000, 120000)
  );
  const startedAt = performance.now();
  const deadlineAt = startedAt + timeoutMs;
  const tab = await _cwaGeminiNotebookFindExactOpenTab(notebookUrl);
  const debuggee = { tabId: tab.id };
  let attached = false;
  let sourceAdmissionMayHaveExecuted = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const before = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookSourceRowsExpression()
    );
    if (
      before?.notebookUrl !== notebookUrl ||
      before?.sourcePanelFound !== true ||
      before?.sourcePickerFound !== true
    ) {
      throw new Error("GEMINI_NOTEBOOK_SOURCE_PANEL_NOT_READY");
    }
    const beforeRows = Array.isArray(before?.rows) ? before.rows : [];
    if (beforeRows.some((row) => !row?.observedRowRef)) {
      throw new Error("GEMINI_NOTEBOOK_PRECOMMIT_ROW_IDENTITY_UNRESOLVED");
    }
    const preRefs = new Set(
      beforeRows.map((row) => String(row.observedRowRef))
    );

    const addSource = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookClickAddSourceExpression()
    );
    if (addSource?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_ADD_SOURCE_OPEN_FAILED:" +
          String(addSource?.reason || "UNKNOWN")
      );
    }

    const firstDialogState = await _cwaGeminiNotebookWaitForDialogState(
      debuggee,
      (state) =>
        state?.directUrlState === true || state?.sitesActionCount === 1,
      deadlineAt,
      "GEMINI_NOTEBOOK_SOURCE_CHOOSER_TIMEOUT"
    );

    if (firstDialogState?.directUrlState !== true) {
      const sites = await _cwaGeminiNotebookMutationEvaluate(
        debuggee,
        _cwaGeminiNotebookClickSitesExpression()
      );
      if (sites?.clicked !== true) {
        throw new Error(
          "GEMINI_NOTEBOOK_SITES_OPEN_FAILED:" +
            String(sites?.reason || "UNKNOWN")
        );
      }
      await _cwaGeminiNotebookWaitForDialogState(
        debuggee,
        (state) => state?.directUrlState === true,
        deadlineAt,
        "GEMINI_NOTEBOOK_URL_SOURCE_DIALOG_TIMEOUT"
      );
    }

    sourceAdmissionMayHaveExecuted = true;
    const written = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookUrlInputExpression(sourceUrl, true)
    );
    if (
      written?.identityResolved !== true ||
      written?.inputMatchesRequested !== true
    ) {
      throw new Error("GEMINI_NOTEBOOK_URL_SOURCE_WRITE_FAILED");
    }

    await _cwaGeminiNotebookWaitForCommitEnabled(
      debuggee,
      sourceUrl,
      deadlineAt
    );

    const committed = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookCommitExpression(sourceUrl)
    );
    if (committed?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_URL_SOURCE_COMMIT_FAILED:" +
          String(committed?.reason || "UNKNOWN")
      );
    }

    const durable = await _cwaGeminiNotebookWaitForDurableSourceRow(
      debuggee,
      notebookUrl,
      preRefs,
      deadlineAt
    );
    const row = durable.row;

    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      capabilityId: CWA_GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID,
      notebookUrl,
      sourceUrl,
      sourceTitle: String(row.title || "").trim(),
      observedRowRef: String(row.observedRowRef),
      sourceRowCountBefore: beforeRows.length,
      sourceRowCountAfter: durable.rowCount,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      finalityEvidence: CWA_GEMINI_NOTEBOOK_FINALITY,
      canonicalCompletionProven: false,
      automaticRetry: false
    };
  } catch (error) {
    if (sourceAdmissionMayHaveExecuted) {
      throw _cwaGeminiNotebookAmbiguousError(error);
    }
    throw error;
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Detach cannot alter the already-classified product outcome.
      }
    }
  }
}

async function _cwaOnNativeMessageWithGeminiNotebook(
  message,
  port,
  next
) {
  const operation = message?.type;
  if (
    message?.protocol !== BRIDGE_PROTOCOL_VERSION ||
    ![
      CWA_GEMINI_NOTEBOOK_ADD_URL_SOURCE_OPERATION,
      CWA_GEMINI_NOTEBOOK_GENERATE_AUDIO_OVERVIEW_OPERATION,
      CWA_GEMINI_NOTEBOOK_OBSERVE_AUDIO_OVERVIEW_OPERATION,
      CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_OPERATION
    ].includes(operation)
  ) {
    return next(message, port);
  }

  const requestId = message.request_id;
  if (typeof requestId !== "string" || !requestId) return;

  const responseType =
    operation === CWA_GEMINI_NOTEBOOK_GENERATE_AUDIO_OVERVIEW_OPERATION
      ? "gemini_notebook_generate_audio_overview_result"
      : operation === CWA_GEMINI_NOTEBOOK_OBSERVE_AUDIO_OVERVIEW_OPERATION
        ? "gemini_notebook_observe_audio_overview_result"
        : operation === CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_OPERATION
          ? "gemini_notebook_audio_artifact_action_probe_result"
          : "gemini_notebook_add_url_source_result";

  try {
    const result =
      operation === CWA_GEMINI_NOTEBOOK_GENERATE_AUDIO_OVERVIEW_OPERATION
        ? await _cwaGeminiNotebookGenerateAudioOverview(message)
        : operation === CWA_GEMINI_NOTEBOOK_OBSERVE_AUDIO_OVERVIEW_OPERATION
          ? await _cwaGeminiNotebookObserveAudioOverview(message)
          : operation === CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_OPERATION
            ? await _cwaGeminiNotebookProbeAudioArtifactAction(message)
            : await _cwaGeminiNotebookAddUrlSource(message);
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: responseType,
      request_id: requestId,
      ok: true,
      ...result
    });
  } catch (error) {
    safePortPost(port, {
      protocol: BRIDGE_PROTOCOL_VERSION,
      type: responseType,
      request_id: requestId,
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    });
  }
}
