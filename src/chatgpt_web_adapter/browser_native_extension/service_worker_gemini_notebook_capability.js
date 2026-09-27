const CWA_GEMINI_NOTEBOOK_PRODUCT_ID = "gemini-notebook-web";
const CWA_GEMINI_NOTEBOOK_ORIGINS = new Set([
  "https://notebook.google.com",
  "https://notebooklm.google.com"
]);

const CWA_GEMINI_NOTEBOOK_ADD_URL_SOURCE_OPERATION =
  "gemini_notebook_add_url_source";
const CWA_GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID = "add_url_source";
const CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_OPERATION =
  "gemini_notebook_audio_overview_probe";
const CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID = "audio_overview";
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


function _cwaGeminiNotebookAudioOverviewProbeExpression() {
  return \`(() => {
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
    const clip = (value, limit = 120) => normalize(value).slice(0, limit);
    const classText = (element) =>
      clip(
        typeof element?.className === "string"
          ? element.className
          : element?.getAttribute?.("class") || "",
        180
      );
    const iconTexts = (element) =>
      Array.from(element?.querySelectorAll?.("mat-icon") || [])
        .slice(0, 5)
        .map((icon) => clip(icon.textContent, 48))
        .filter(Boolean);
    const descriptor = (element, includeText) => ({
      tag: String(element?.tagName || "").toLowerCase(),
      id: clip(element?.id || "", 160),
      className: classText(element),
      role: clip(element?.getAttribute?.("role") || "", 48),
      ariaLabel: clip(element?.getAttribute?.("aria-label") || "", 160),
      title: clip(element?.getAttribute?.("title") || "", 160),
      text: includeText ? clip(element?.innerText || element?.textContent || "", 180) : "",
      disabled:
        "disabled" in element
          ? Boolean(element.disabled)
          : element?.getAttribute?.("aria-disabled") === "true",
      icons: iconTexts(element)
    });
    const ancestorPath = (element) => {
      const result = [];
      let current = element?.parentElement || null;
      while (current instanceof Element && result.length < 5) {
        result.push({
          tag: String(current.tagName || "").toLowerCase(),
          id: clip(current.id || "", 120),
          className: classText(current),
          role: clip(current.getAttribute("role") || "", 48)
        });
        current = current.parentElement;
      }
      return result;
    };

    const notebookUrl =
      location.origin + location.pathname.replace(/\\/$/, "");
    const sourcePanel = document.querySelector("section.source-panel");
    const sourcePicker = sourcePanel?.querySelector("source-picker") || null;
    const sourceRowCount =
      sourcePicker instanceof Element
        ? sourcePicker.querySelectorAll(".single-source-container").length
        : 0;

    const controls = Array.from(
      document.querySelectorAll(
        "button,[role='button'],[aria-label],[title]"
      )
    ).filter(visible);

    const targetPattern =
      /(audio|overview|studio|podcast|headphone|listen|generate|аудио|обзор|студи|созд|сгенер)/i;
    const targetControls = [];
    for (const control of controls) {
      const icons = iconTexts(control);
      const semantic = normalize(
        [
          control.id,
          classText(control),
          control.getAttribute("role"),
          control.getAttribute("aria-label"),
          control.getAttribute("title"),
          control.innerText,
          control.textContent,
          ...icons
        ].join(" ")
      );
      if (!targetPattern.test(semantic)) continue;
      targetControls.push({
        ...descriptor(control, true),
        ancestors: ancestorPath(control)
      });
      if (targetControls.length >= 30) break;
    }

    const controlSample = controls.slice(0, 60).map((control) => ({
      ...descriptor(control, false),
      ancestors: ancestorPath(control).slice(0, 2)
    }));

    const regionCandidates = Array.from(
      document.querySelectorAll(
        "section,aside,[role='region'],[role='complementary']," +
          "mat-card,mat-expansion-panel"
      )
    )
      .filter(visible)
      .slice(0, 40)
      .map((region) => ({
        tag: String(region.tagName || "").toLowerCase(),
        id: clip(region.id || "", 120),
        className: classText(region),
        role: clip(region.getAttribute("role") || "", 48),
        ariaLabel: clip(region.getAttribute("aria-label") || "", 160),
        title: clip(region.getAttribute("title") || "", 160),
        buttonCount: region.querySelectorAll("button,[role='button']").length
      }));

    return {
      notebookUrl,
      sourcePanelFound: sourcePanel instanceof Element,
      sourcePickerFound: sourcePicker instanceof Element,
      sourceRowCount,
      targetControls,
      controlSample,
      regionCandidates,
      rawDomExported: false,
      writePerformed: false,
      navigationPerformed: false
    };
  })()\`;
}

async function _cwaGeminiNotebookProbeAudioOverview(message) {
  if (message?.productId !== CWA_GEMINI_NOTEBOOK_PRODUCT_ID) {
    throw new Error("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH");
  }
  if (message?.probeId !== CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID) {
    throw new Error("GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID_MISMATCH");
  }

  const notebookUrl = _cwaGeminiNotebookCanonicalNotebookUrl(
    message?.notebookUrl
  );
  if (!notebookUrl) {
    throw new Error("GEMINI_NOTEBOOK_NOTEBOOK_URL_INVALID");
  }

  const startedAt = performance.now();
  const tab = await _cwaGeminiNotebookFindExactOpenTab(notebookUrl);
  const debuggee = { tabId: tab.id };
  let attached = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const snapshot = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookAudioOverviewProbeExpression()
    );
    if (snapshot?.notebookUrl !== notebookUrl) {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_OVERVIEW_NOTEBOOK_IDENTITY_MISMATCH");
    }

    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      probeId: CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_ID,
      notebookUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      sourcePanelFound: snapshot?.sourcePanelFound === true,
      sourcePickerFound: snapshot?.sourcePickerFound === true,
      sourceRowCount: Number.isInteger(snapshot?.sourceRowCount)
        ? snapshot.sourceRowCount
        : 0,
      targetControls: Array.isArray(snapshot?.targetControls)
        ? snapshot.targetControls
        : [],
      controlSample: Array.isArray(snapshot?.controlSample)
        ? snapshot.controlSample
        : [],
      regionCandidates: Array.isArray(snapshot?.regionCandidates)
        ? snapshot.regionCandidates
        : [],
      rawDomExported: false,
      writePerformed: false,
      navigationPerformed: false
    };
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Read-only characterization cannot change product state on detach.
      }
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
      CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_OPERATION
    ].includes(operation)
  ) {
    return next(message, port);
  }

  const requestId = message.request_id;
  if (typeof requestId !== "string" || !requestId) return;

  const responseType =
    operation === CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_OPERATION
      ? "gemini_notebook_audio_overview_probe_result"
      : "gemini_notebook_add_url_source_result";

  try {
    const result =
      operation === CWA_GEMINI_NOTEBOOK_AUDIO_OVERVIEW_PROBE_OPERATION
        ? await _cwaGeminiNotebookProbeAudioOverview(message)
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
