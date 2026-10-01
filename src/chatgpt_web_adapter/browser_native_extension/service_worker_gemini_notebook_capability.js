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
const CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PROBE_OPERATION =
  "gemini_notebook_audio_artifact_menu_probe";
const CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_INTENT_PROBE_OPERATION =
  "gemini_notebook_audio_artifact_download_intent_probe";
const CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROBE_OPERATION =
  "gemini_notebook_audio_artifact_byte_probe";
const CWA_GEMINI_NOTEBOOK_STUDIO_CREATION_CONTROLS_PROBE_OPERATION =
  "gemini_notebook_studio_creation_controls_probe";
const CWA_GEMINI_NOTEBOOK_VIDEO_CONFIG_PROBE_OPERATION =
  "gemini_notebook_video_config_probe";
const CWA_GEMINI_NOTEBOOK_VIDEO_GENERATION_PROBE_OPERATION =
  "gemini_notebook_video_generation_probe";
const CWA_GEMINI_NOTEBOOK_VIDEO_ARTIFACT_OBSERVE_PROBE_OPERATION =
  "gemini_notebook_video_artifact_observe_probe";
const CWA_GEMINI_NOTEBOOK_VIDEO_PENDING_EVIDENCE =
  "PAGE_DOM_BACKGROUND_VIDEO_ARTIFACT_PENDING";
const CWA_GEMINI_NOTEBOOK_VIDEO_COMPLETION_FINALITY =
  "PAGE_DOM_DURABLE_BACKGROUND_VIDEO_ARTIFACT_COMPLETION";
const CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_CHUNK_TYPE =
  "gemini_notebook_audio_artifact_byte_chunk";
const CWA_GEMINI_NOTEBOOK_AUDIO_BYTE_CHUNK_BASE64_CHARS = 600_000;
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




function _cwaGeminiNotebookStudioCreationControlsExpression() {
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
        .slice(0, 12)
        .map((icon) => clip(icon.textContent, 48))
        .filter(Boolean);

    const notebookUrl =
      location.origin + location.pathname.replace(/\\/$/, "");
    const studio = document.querySelector("section.studio-panel");
    const controls = [];

    if (studio instanceof Element && visible(studio)) {
      const owners = Array.from(
        studio.querySelectorAll("basic-create-artifact-button")
      ).slice(0, 24);

      for (let index = 0; index < owners.length; index += 1) {
        const owner = owners[index];
        if (!visible(owner)) continue;
        const control =
          owner.querySelector("[role='button']") ||
          owner.querySelector("button") ||
          null;
        if (!(control instanceof Element) || !visible(control)) continue;

        controls.push({
          index,
          ownerTag: String(owner.tagName || "").toLowerCase(),
          ownerClassName: classText(owner),
          controlTag: String(control.tagName || "").toLowerCase(),
          controlClassName: classText(control),
          role: clip(control.getAttribute("role") || "", 48),
          ariaLabel: clip(control.getAttribute("aria-label") || "", 180),
          title: clip(control.getAttribute("title") || "", 180),
          text: clip(control.innerText || control.textContent || "", 180),
          disabled:
            "disabled" in control
              ? Boolean(control.disabled)
              : control.getAttribute("aria-disabled") === "true",
          icons: iconTexts(control)
        });
      }
    }

    return {
      notebookUrl,
      studioFound: studio instanceof Element && visible(studio),
      controls
    };
  })()`;
}

async function _cwaGeminiNotebookProbeStudioCreationControls(message) {
  if (message?.productId !== CWA_GEMINI_NOTEBOOK_PRODUCT_ID) {
    throw new Error("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH");
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

    const state = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookStudioCreationControlsExpression()
    );
    if (state?.notebookUrl !== notebookUrl) {
      throw new Error("GEMINI_NOTEBOOK_STUDIO_PROBE_ROUTE_MISMATCH");
    }
    if (state?.studioFound !== true) {
      throw new Error("GEMINI_NOTEBOOK_STUDIO_OWNER_MISSING");
    }

    const controls = Array.isArray(state?.controls)
      ? state.controls.slice(0, 24)
      : [];

    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      notebookUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      studioFound: true,
      creationControls: controls,
      writePerformed: false,
      navigationPerformed: false,
      rawDomExported: false
    };
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Read-only characterization cleanup has no product effect.
      }
    }
  }
}


function _cwaGeminiNotebookClickVideoOverviewExpression() {
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
          entry.icons.includes("videocam")
      );

    if (candidates.length !== 1) {
      return {
        clicked: false,
        reason: "VIDEO_CREATE_CONTROL_IDENTITY_UNRESOLVED",
        candidateCount: candidates.length
      };
    }

    const control = candidates[0].control;
    if (
      control.getAttribute("aria-disabled") === "true" ||
      ("disabled" in control && Boolean(control.disabled))
    ) {
      return { clicked: false, reason: "VIDEO_CREATE_CONTROL_DISABLED" };
    }

    control.click();
    return { clicked: true };
  })()`;
}

function _cwaGeminiNotebookVisibleDialogInventoryExpression() {
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
    const clip = (value, limit = 220) => normalize(value).slice(0, limit);
    const classText = (element) =>
      clip(
        typeof element?.className === "string"
          ? element.className
          : element?.getAttribute?.("class") || "",
        180
      );
    const iconTexts = (element, limit = 12) =>
      Array.from(element?.querySelectorAll?.("mat-icon") || [])
        .slice(0, limit)
        .map((icon) => clip(icon.textContent, 48))
        .filter(Boolean);

    const dialogs = Array.from(
      document.querySelectorAll(
        "mat-dialog-container[role='dialog'],[role='dialog']"
      )
    )
      .filter(visible)
      .slice(0, 4)
      .map((dialog, index) => {
        const controls = Array.from(
          dialog.querySelectorAll("button,[role='button']")
        )
          .filter(visible)
          .slice(0, 20)
          .map((control, controlIndex) => ({
            index: controlIndex,
            tag: String(control.tagName || "").toLowerCase(),
            className: classText(control),
            role: clip(control.getAttribute("role") || "", 48),
            ariaLabel: clip(control.getAttribute("aria-label") || "", 180),
            title: clip(control.getAttribute("title") || "", 180),
            text: clip(control.innerText || control.textContent || "", 220),
            disabled:
              "disabled" in control
                ? Boolean(control.disabled)
                : control.getAttribute("aria-disabled") === "true",
            icons: iconTexts(control, 8)
          }));

        return {
          index,
          tag: String(dialog.tagName || "").toLowerCase(),
          className: classText(dialog),
          role: clip(dialog.getAttribute("role") || "", 48),
          ariaLabel: clip(dialog.getAttribute("aria-label") || "", 180),
          title: clip(dialog.getAttribute("title") || "", 180),
          text: clip(dialog.innerText || dialog.textContent || "", 600),
          icons: iconTexts(dialog, 16),
          controls
        };
      });

    return { dialogs };
  })()`;
}

async function _cwaGeminiNotebookProbeVideoConfig(message) {
  if (message?.productId !== CWA_GEMINI_NOTEBOOK_PRODUCT_ID) {
    throw new Error("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH");
  }

  const notebookUrl = _cwaGeminiNotebookCanonicalNotebookUrl(
    message?.notebookUrl
  );
  if (!notebookUrl) {
    throw new Error("GEMINI_NOTEBOOK_NOTEBOOK_URL_INVALID");
  }

  const timeoutMs = Math.max(
    3000,
    Math.min(Number(message?.timeoutMs) || 15000, 30000)
  );
  const startedAt = performance.now();
  const deadlineAt = startedAt + timeoutMs;
  const tab = await _cwaGeminiNotebookFindExactOpenTab(notebookUrl);
  const debuggee = { tabId: tab.id };
  let attached = false;
  let configurationOpenMayHaveExecuted = false;

  const artifactRefs = (state) =>
    Array.isArray(state?.rows)
      ? state.rows
          .map((row) => String(row?.observedArtifactRef || ""))
          .filter(Boolean)
          .sort()
      : [];

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const initialDialogs = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookVisibleDialogInventoryExpression()
    );
    const initialDialogList = Array.isArray(initialDialogs?.dialogs)
      ? initialDialogs.dialogs
      : [];
    if (initialDialogList.length !== 0) {
      throw new Error(
        "GEMINI_NOTEBOOK_VIDEO_CONFIG_PRESTATE_DIALOG_OPEN:" +
          String(initialDialogList.length)
      );
    }

    const beforeArtifacts = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookAudioArtifactItemsExpression()
    );
    if (beforeArtifacts?.notebookUrl !== notebookUrl) {
      throw new Error("GEMINI_NOTEBOOK_VIDEO_CONFIG_ROUTE_MISMATCH");
    }
    const beforeArtifactRefs = artifactRefs(beforeArtifacts);

    configurationOpenMayHaveExecuted = true;
    const clicked = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookClickVideoOverviewExpression()
    );
    if (clicked?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_VIDEO_CREATE_CONTROL_CLICK_FAILED:" +
          String(clicked?.reason || "UNKNOWN")
      );
    }

    let dialog = null;
    while (performance.now() < deadlineAt) {
      const state = await _cwaGeminiNotebookMutationEvaluate(
        debuggee,
        _cwaGeminiNotebookVisibleDialogInventoryExpression()
      );
      const dialogs = Array.isArray(state?.dialogs) ? state.dialogs : [];
      if (dialogs.length > 1) {
        throw new Error(
          "GEMINI_NOTEBOOK_VIDEO_CONFIG_DIALOG_AMBIGUOUS:" +
            String(dialogs.length)
        );
      }
      if (dialogs.length === 1) {
        dialog = dialogs[0];
        break;
      }
      await sleep(100);
    }
    if (!dialog) {
      throw new Error("GEMINI_NOTEBOOK_VIDEO_CONFIG_DIALOG_TIMEOUT");
    }

    const afterArtifacts = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookAudioArtifactItemsExpression()
    );
    if (afterArtifacts?.notebookUrl !== notebookUrl) {
      throw new Error("GEMINI_NOTEBOOK_VIDEO_CONFIG_ROUTE_MISMATCH");
    }
    const afterArtifactRefs = artifactRefs(afterArtifacts);
    const artifactLibraryUnchanged =
      JSON.stringify(beforeArtifactRefs) === JSON.stringify(afterArtifactRefs);
    if (!artifactLibraryUnchanged) {
      throw new Error(
        "GEMINI_NOTEBOOK_VIDEO_CONFIG_ARTIFACT_LIBRARY_CHANGED"
      );
    }

    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      notebookUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      createControlIcon: "videocam",
      configurationSurfaceObserved: true,
      dialog,
      beforeArtifactRefs,
      afterArtifactRefs,
      artifactLibraryUnchanged: true,
      configurationOpenClickPerformed: true,
      generationStartedProven: false,
      durableProductWriteProven: false,
      navigationPerformed: false,
      automaticRetry: false,
      rawDomExported: false
    };
  } catch (error) {
    if (configurationOpenMayHaveExecuted) {
      throw _cwaGeminiNotebookAmbiguousError(error);
    }
    throw error;
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Detach cannot change the already-classified config observation.
      }
    }
  }
}


function _cwaGeminiNotebookVideoConfigReadinessExpression() {
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
    if (dialogs.length !== 1) {
      return {
        ready: false,
        dialogCount: dialogs.length,
        tonalCandidateCount: 0
      };
    }

    const dialog = dialogs[0];
    const icons = Array.from(dialog.querySelectorAll("mat-icon")).map(
      (icon) => String(icon.textContent || "").trim()
    );
    if (!icons.includes("subscriptions")) {
      return {
        ready: false,
        dialogCount: 1,
        dialogOwnerProven: false,
        tonalCandidateCount: 0
      };
    }

    const actualButtons = Array.from(
      dialog.querySelectorAll("button")
    ).filter(visible);
    const tonalCandidates = actualButtons.filter(
      (button) =>
        button.classList.contains("mat-tonal-button") &&
        !button.disabled &&
        button.getAttribute("aria-disabled") !== "true"
    );
    return {
      ready: tonalCandidates.length === 1,
      dialogCount: 1,
      dialogOwnerProven: true,
      actualButtonCount: actualButtons.length,
      tonalCandidateCount: tonalCandidates.length
    };
  })()`;
}

function _cwaGeminiNotebookClickVideoGenerateNowExpression() {
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
    if (dialogs.length !== 1) {
      return {
        clicked: false,
        reason: "VIDEO_CONFIG_DIALOG_IDENTITY_UNRESOLVED",
        dialogCount: dialogs.length
      };
    }

    const dialog = dialogs[0];
    const icons = Array.from(dialog.querySelectorAll("mat-icon")).map(
      (icon) => String(icon.textContent || "").trim()
    );
    if (!icons.includes("subscriptions")) {
      return {
        clicked: false,
        reason: "VIDEO_CONFIG_DIALOG_OWNER_UNRESOLVED"
      };
    }

    const actualButtons = Array.from(
      dialog.querySelectorAll("button")
    ).filter(visible);
    const tonalCandidates = actualButtons.filter(
      (button) =>
        button.classList.contains("mat-tonal-button") &&
        !button.disabled &&
        button.getAttribute("aria-disabled") !== "true"
    );
    if (tonalCandidates.length !== 1) {
      return {
        clicked: false,
        reason: "VIDEO_GENERATE_NOW_IDENTITY_UNRESOLVED",
        actualButtonCount: actualButtons.length,
        tonalCandidateCount: tonalCandidates.length
      };
    }

    tonalCandidates[0].click();
    return { clicked: true };
  })()`;
}

async function _cwaGeminiNotebookWaitForVideoConfig(debuggee, deadlineAt) {
  while (performance.now() < deadlineAt) {
    const state = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookVideoConfigReadinessExpression()
    );
    if (state?.ready === true) return state;
    await sleep(100);
  }
  throw new Error("GEMINI_NOTEBOOK_VIDEO_CONFIG_TIMEOUT");
}

async function _cwaGeminiNotebookWaitForStableArtifactDelta(
  debuggee,
  notebookUrl,
  beforeRefs,
  deadlineAt
) {
  const before = new Set(beforeRefs);
  let stableSignature = null;
  let stableSince = null;
  let lastNewCount = -1;

  while (performance.now() < deadlineAt) {
    const state = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookAudioArtifactItemsExpression()
    );
    if (state?.notebookUrl !== notebookUrl) {
      throw new Error("GEMINI_NOTEBOOK_VIDEO_NOTEBOOK_ROUTE_CHANGED");
    }
    if (
      state?.studioFound !== true ||
      state?.containerFound !== true ||
      state?.libraryFound !== true
    ) {
      throw new Error("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_LIBRARY_NOT_READY");
    }

    const rows = Array.isArray(state?.rows) ? state.rows : [];
    const newRows = rows.filter(
      (row) =>
        row?.observedArtifactRef &&
        !before.has(String(row.observedArtifactRef))
    );
    lastNewCount = newRows.length;

    if (newRows.length > 1) {
      throw new Error(
        "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_DELTA_AMBIGUOUS:" +
          String(newRows.length)
      );
    }
    if (newRows.length === 0) {
      stableSignature = null;
      stableSince = null;
      await sleep(200);
      continue;
    }

    const row = newRows[0];
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
    "GEMINI_NOTEBOOK_VIDEO_ARTIFACT_DELTA_TIMEOUT:new=" +
      String(lastNewCount)
  );
}

async function _cwaGeminiNotebookProbeVideoGeneration(message) {
  if (message?.productId !== CWA_GEMINI_NOTEBOOK_PRODUCT_ID) {
    throw new Error("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH");
  }

  const notebookUrl = _cwaGeminiNotebookCanonicalNotebookUrl(
    message?.notebookUrl
  );
  if (!notebookUrl) {
    throw new Error("GEMINI_NOTEBOOK_NOTEBOOK_URL_INVALID");
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
  let generationCommitMayHaveExecuted = false;

  const artifactRefs = (state) =>
    Array.isArray(state?.rows)
      ? state.rows
          .map((row) => String(row?.observedArtifactRef || ""))
          .filter(Boolean)
          .sort()
      : [];

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const initialDialogs = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookVisibleDialogInventoryExpression()
    );
    const initialDialogList = Array.isArray(initialDialogs?.dialogs)
      ? initialDialogs.dialogs
      : [];
    if (initialDialogList.length !== 0) {
      throw new Error(
        "GEMINI_NOTEBOOK_VIDEO_GENERATION_PRESTATE_DIALOG_OPEN:" +
          String(initialDialogList.length)
      );
    }

    const before = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookAudioArtifactItemsExpression()
    );
    if (
      before?.notebookUrl !== notebookUrl ||
      before?.studioFound !== true ||
      before?.containerFound !== true ||
      before?.libraryFound !== true
    ) {
      throw new Error("GEMINI_NOTEBOOK_VIDEO_GENERATION_PRESTATE_INVALID");
    }
    const beforeArtifactRefs = artifactRefs(before);

    const opened = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookClickVideoOverviewExpression()
    );
    if (opened?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_VIDEO_CONFIG_OPEN_FAILED:" +
          String(opened?.reason || "UNKNOWN")
      );
    }

    await _cwaGeminiNotebookWaitForVideoConfig(debuggee, deadlineAt);

    generationCommitMayHaveExecuted = true;
    const committed = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookClickVideoGenerateNowExpression()
    );
    if (committed?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_VIDEO_GENERATE_CLICK_FAILED:" +
          String(committed?.reason || "UNKNOWN")
      );
    }

    const accepted = await _cwaGeminiNotebookWaitForStableArtifactDelta(
      debuggee,
      notebookUrl,
      beforeArtifactRefs,
      deadlineAt
    );
    const row = accepted.row;
    const afterArtifactRefs = artifactRefs(accepted.state);

    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      notebookUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      beforeArtifactRefs,
      afterArtifactRefs,
      generationCommitMayHaveExecuted: true,
      generationAcceptedProven: true,
      observedArtifactRef: String(row.observedArtifactRef),
      artifactStatus:
        row.statusCandidate === "PENDING_CANDIDATE"
          ? "PENDING"
          : "COMPLETION_CANDIDATE",
      artifactTitle: String(row.title || ""),
      artifactDetails: String(row.details || ""),
      artifactIcons: Array.isArray(row.icons) ? row.icons : [],
      startEvidence: "PAGE_DOM_BACKGROUND_VIDEO_ARTIFACT_ACCEPTED",
      canonicalCompletionProven: false,
      automaticRetry: false,
      navigationPerformed: false
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
      } catch {
        // Detach cannot change the already-classified generation outcome.
      }
    }
  }
}


async function _cwaGeminiNotebookWaitForStableExactArtifact(
  debuggee,
  notebookUrl,
  expectedArtifactRef,
  deadlineAt
) {
  let stableSignature = null;
  let stableSince = null;
  let lastRowCount = -1;
  let lastMatchCount = -1;

  while (performance.now() < deadlineAt) {
    const state = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookAudioArtifactItemsExpression()
    );
    if (state?.notebookUrl !== notebookUrl) {
      throw new Error("GEMINI_NOTEBOOK_EXACT_ARTIFACT_ROUTE_CHANGED");
    }
    if (
      state?.studioFound !== true ||
      state?.containerFound !== true ||
      state?.libraryFound !== true
    ) {
      throw new Error("GEMINI_NOTEBOOK_EXACT_ARTIFACT_LIBRARY_NOT_READY");
    }

    const rows = Array.isArray(state?.rows) ? state.rows : [];
    lastRowCount = rows.length;
    const matches = rows.filter(
      (row) =>
        String(row?.observedArtifactRef || "") === expectedArtifactRef
    );
    lastMatchCount = matches.length;

    if (matches.length > 1) {
      throw new Error(
        "GEMINI_NOTEBOOK_EXACT_ARTIFACT_IDENTITY_AMBIGUOUS:" +
          String(matches.length)
      );
    }
    if (matches.length === 0) {
      stableSignature = null;
      stableSince = null;
      await sleep(200);
      continue;
    }

    const row = matches[0];
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
    "GEMINI_NOTEBOOK_EXACT_ARTIFACT_STABLE_TIMEOUT:rows=" +
      String(lastRowCount) +
      ":matches=" +
      String(lastMatchCount)
  );
}

async function _cwaGeminiNotebookProbeVideoArtifactObservation(message) {
  if (message?.productId !== CWA_GEMINI_NOTEBOOK_PRODUCT_ID) {
    throw new Error("GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH");
  }

  const notebookUrl = _cwaGeminiNotebookCanonicalNotebookUrl(
    message?.notebookUrl
  );
  if (!notebookUrl) {
    throw new Error("GEMINI_NOTEBOOK_NOTEBOOK_URL_INVALID");
  }

  const observedArtifactRef =
    typeof message?.observedArtifactRef === "string" &&
    /^[A-Za-z0-9_-]{8,200}$/.test(message.observedArtifactRef)
      ? message.observedArtifactRef
      : null;
  if (!observedArtifactRef) {
    throw new Error("GEMINI_NOTEBOOK_VIDEO_ARTIFACT_REF_INVALID");
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

    const beforeReload = await _cwaGeminiNotebookWaitForStableExactArtifact(
      debuggee,
      notebookUrl,
      observedArtifactRef,
      deadlineAt
    );
    const firstRow = beforeReload.row;

    if (firstRow.statusCandidate === "PENDING_CANDIDATE") {
      return {
        productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
        notebookUrl,
        tabId: tab.id,
        elapsedMs: Math.round(performance.now() - startedAt),
        observedArtifactRef,
        artifactStatus: "PENDING",
        artifactTitle: String(firstRow.title || ""),
        artifactDetails: String(firstRow.details || ""),
        artifactIcons: Array.isArray(firstRow.icons) ? firstRow.icons : [],
        completionProven: false,
        reloadVerified: false,
        finalityEvidence: CWA_GEMINI_NOTEBOOK_VIDEO_PENDING_EVIDENCE,
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

    const afterReload = await _cwaGeminiNotebookWaitForStableExactArtifact(
      debuggee,
      notebookUrl,
      observedArtifactRef,
      deadlineAt
    );
    const durableRow = afterReload.row;
    if (durableRow.statusCandidate !== "NON_PENDING_CANDIDATE") {
      throw new Error(
        "GEMINI_NOTEBOOK_VIDEO_DURABLE_COMPLETION_NOT_CONFIRMED"
      );
    }

    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      notebookUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      observedArtifactRef,
      artifactStatus: "COMPLETED",
      artifactTitle: String(durableRow.title || ""),
      artifactDetails: String(durableRow.details || ""),
      artifactIcons: Array.isArray(durableRow.icons)
        ? durableRow.icons
        : [],
      completionProven: true,
      reloadVerified: true,
      finalityEvidence: CWA_GEMINI_NOTEBOOK_VIDEO_COMPLETION_FINALITY,
      canonicalCompletionProven: false,
      automaticRetry: false,
      writePerformed: false,
      navigationPerformed: true
    };
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Observation is read-only; detach cannot change product finality.
      }
    }
  }
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
    const expectedArtifactRef = ${encodedArtifactRef};
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


function _cwaGeminiNotebookVisibleArtifactMenusExpression() {
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

    const panels = Array.from(
      document.querySelectorAll("[role='menu'],.mat-mdc-menu-panel")
    )
      .filter(visible)
      .slice(0, 8)
      .map((panel) => ({
        tag: String(panel.tagName || "").toLowerCase(),
        id: clip(panel.id || "", 140),
        className: classText(panel),
        role: clip(panel.getAttribute("role") || "", 48),
        ariaLabel: clip(panel.getAttribute("aria-label") || "", 160),
        items: Array.from(
          panel.querySelectorAll(
            "button,[role='menuitem'],a[role='menuitem']"
          )
        )
          .filter(visible)
          .slice(0, 24)
          .map((item, index) => ({
            index,
            tag: String(item.tagName || "").toLowerCase(),
            id: clip(item.id || "", 120),
            className: classText(item),
            role: clip(item.getAttribute("role") || "", 48),
            ariaLabel: clip(item.getAttribute("aria-label") || "", 160),
            title: clip(item.getAttribute("title") || "", 160),
            text: clip(item.innerText || item.textContent || "", 180),
            disabled:
              "disabled" in item
                ? Boolean(item.disabled)
                : item.getAttribute("aria-disabled") === "true",
            icons: iconTexts(item)
          }))
      }));

    return { panels };
  })()`;
}

function _cwaGeminiNotebookClickExactArtifactMoreMenuExpression(
  expectedArtifactRef
) {
  const encodedArtifactRef = JSON.stringify(expectedArtifactRef);
  return `(() => {
    const expectedArtifactRef = ${encodedArtifactRef};
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

    const studio = document.querySelector("section.studio-panel");
    const library =
      studio?.querySelector(".artifact-library-container artifact-library") ||
      null;
    if (!(library instanceof Element)) {
      return { clicked: false, reason: "ARTIFACT_LIBRARY_MISSING" };
    }

    const matches = [];
    for (const row of library.querySelectorAll(".artifact-item-button")) {
      if (!visible(row)) continue;
      const labels = row.querySelector("[id^='artifact-labels-']");
      const labelsId = String(labels?.id || "");
      const prefix = "artifact-labels-";
      const observedArtifactRef = labelsId.startsWith(prefix)
        ? labelsId.slice(prefix.length)
        : null;
      if (observedArtifactRef === expectedArtifactRef) matches.push(row);
    }
    if (matches.length !== 1) {
      return {
        clicked: false,
        reason: "ARTIFACT_ROW_IDENTITY_UNRESOLVED",
        matchCount: matches.length
      };
    }

    const row = matches[0];
    const candidates = Array.from(
      row.querySelectorAll("button,[role='button']")
    ).filter((control) => {
      if (!visible(control)) return false;
      const icons = Array.from(control.querySelectorAll("mat-icon")).map(
        (icon) => String(icon.textContent || "").trim()
      );
      const owner = control.closest("nb-icon-button.artifact-more-button");
      return (
        icons.includes("more_vert") &&
        control.classList.contains("mat-mdc-menu-trigger") &&
        owner instanceof Element
      );
    });

    if (candidates.length !== 1) {
      return {
        clicked: false,
        reason: "ARTIFACT_MORE_MENU_IDENTITY_UNRESOLVED",
        candidateCount: candidates.length
      };
    }

    const control = candidates[0];
    if (
      control.getAttribute("aria-disabled") === "true" ||
      ("disabled" in control && Boolean(control.disabled))
    ) {
      return { clicked: false, reason: "ARTIFACT_MORE_MENU_DISABLED" };
    }

    control.click();
    return {
      clicked: true,
      ariaControls: String(control.getAttribute("aria-controls") || ""),
      ariaExpanded: String(control.getAttribute("aria-expanded") || "")
    };
  })()`;
}

async function _cwaGeminiNotebookProbeAudioArtifactMenu(message) {
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

  const timeoutMs = Math.max(
    3000,
    Math.min(Number(message?.timeoutMs) || 15000, 30000)
  );
  const startedAt = performance.now();
  const deadlineAt = startedAt + timeoutMs;
  const tab = await _cwaGeminiNotebookFindExactOpenTab(notebookUrl);
  const debuggee = { tabId: tab.id };
  let attached = false;
  let menuClickPerformed = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const beforeMenus = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookVisibleArtifactMenusExpression()
    );
    const beforePanels = Array.isArray(beforeMenus?.panels)
      ? beforeMenus.panels
      : [];
    if (beforePanels.length !== 0) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PRESTATE_NOT_EMPTY:" +
          String(beforePanels.length)
      );
    }

    menuClickPerformed = true;
    const clicked = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookClickExactArtifactMoreMenuExpression(
        expectedArtifactRef
      )
    );
    if (clicked?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_CLICK_FAILED:" +
          String(clicked?.reason || "UNKNOWN")
      );
    }

    let observed = null;
    while (performance.now() < deadlineAt) {
      const state = await _cwaGeminiNotebookMutationEvaluate(
        debuggee,
        _cwaGeminiNotebookVisibleArtifactMenusExpression()
      );
      const panels = Array.isArray(state?.panels) ? state.panels : [];
      if (panels.length > 1) {
        throw new Error(
          "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_IDENTITY_AMBIGUOUS:" +
            String(panels.length)
        );
      }
      if (panels.length === 1 && Array.isArray(panels[0]?.items)) {
        observed = panels[0];
        break;
      }
      await sleep(100);
    }

    if (!observed) {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_TIMEOUT");
    }

    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      notebookUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      observedArtifactRef: expectedArtifactRef,
      menuTriggerAriaControls: String(clicked?.ariaControls || ""),
      menuTriggerAriaExpanded: String(clicked?.ariaExpanded || ""),
      menu: observed,
      menuClickPerformed: true,
      productWritePerformed: false,
      navigationPerformed: false,
      downloadPerformed: false,
      rawDomExported: false
    };
  } catch (error) {
    if (menuClickPerformed) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_OBSERVATION_FAILED_AFTER_CLICK:" +
          String(error instanceof Error ? error.message : error)
      );
    }
    throw error;
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Menu-open characterization has no durable product effect.
      }
    }
  }
}


function _cwaGeminiNotebookClickVisibleArtifactDownloadExpression() {
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

    const panels = Array.from(
      document.querySelectorAll("[role='menu'],.mat-mdc-menu-panel")
    ).filter(visible);
    if (panels.length !== 1) {
      return {
        clicked: false,
        reason: "ARTIFACT_MENU_IDENTITY_UNRESOLVED",
        panelCount: panels.length
      };
    }

    const candidates = Array.from(
      panels[0].querySelectorAll(
        "button,[role='menuitem'],a[role='menuitem']"
      )
    ).filter((item) => {
      if (!visible(item)) return false;
      const icons = Array.from(item.querySelectorAll("mat-icon")).map(
        (icon) => String(icon.textContent || "").trim()
      );
      return (
        String(item.tagName || "").toLowerCase() === "button" &&
        item.getAttribute("role") === "menuitem" &&
        item.classList.contains("mat-mdc-menu-item") &&
        icons.includes("save_alt") &&
        !item.disabled &&
        item.getAttribute("aria-disabled") !== "true"
      );
    });

    if (candidates.length !== 1) {
      return {
        clicked: false,
        reason: "ARTIFACT_DOWNLOAD_ACTION_IDENTITY_UNRESOLVED",
        candidateCount: candidates.length
      };
    }

    candidates[0].click();
    return { clicked: true };
  })()`;
}


function _cwaGeminiNotebookInstallDownloadSinkProbeExpression() {
  return `(() => {
    const key = "__cwaGeminiNotebookDownloadSinkProbeV1";
    if (window[key]?.installed === true) {
      return { installed: false, reason: "ALREADY_INSTALLED" };
    }

    const clip = (value, limit = 160) =>
      String(value || "").replace(/\\s+/g, " ").trim().slice(0, limit);
    const sanitizeUrl = (value) => {
      try {
        const parsed = new URL(String(value || ""), location.href);
        return {
          scheme: clip(parsed.protocol, 24),
          origin: clip(parsed.origin, 160),
          hasQuery: Boolean(parsed.search),
          pathSuffix: String(parsed.pathname || "")
            .split("/")
            .filter(Boolean)
            .slice(-3)
            .map((part) => clip(part, 100))
        };
      } catch {
        return {
          scheme: "",
          origin: "",
          hasQuery: false,
          pathSuffix: []
        };
      }
    };

    const state = {
      installed: true,
      events: [],
      privateWindowOpenLocators: [],
      originalWindowOpen: window.open,
      originalCreateObjectURL:
        typeof URL.createObjectURL === "function"
          ? URL.createObjectURL
          : null,
      windowOpenPatched: false,
      objectUrlPatched: false,
      onClick: null,
      onSubmit: null
    };
    const pushEvent = (entry) => {
      if (state.events.length < 12) state.events.push(entry);
    };

    state.onClick = (event) => {
      const target =
        event?.target instanceof Element ? event.target : null;
      const anchor = target?.closest?.("a[href]") || null;
      if (!(anchor instanceof HTMLAnchorElement)) return;

      pushEvent({
        kind: "anchor_click",
        url: sanitizeUrl(anchor.href),
        downloadPresent: anchor.hasAttribute("download"),
        downloadValue: clip(anchor.getAttribute("download") || "", 160),
        target: clip(anchor.getAttribute("target") || "", 48),
        trusted: event.isTrusted === true
      });
      event.preventDefault();
      event.stopImmediatePropagation();
    };

    state.onSubmit = (event) => {
      const form =
        event?.target instanceof HTMLFormElement ? event.target : null;
      if (!(form instanceof HTMLFormElement)) return;
      pushEvent({
        kind: "form_submit",
        url: sanitizeUrl(form.action || location.href),
        method: clip(form.method || "", 24),
        target: clip(form.target || "", 48),
        trusted: event.isTrusted === true
      });
      event.preventDefault();
      event.stopImmediatePropagation();
    };

    document.addEventListener("click", state.onClick, true);
    document.addEventListener("submit", state.onSubmit, true);

    try {
      window.open = function(url, target) {
        const privateLocator = String(url || "");
        if (
          privateLocator &&
          state.privateWindowOpenLocators.length < 4
        ) {
          state.privateWindowOpenLocators.push(privateLocator);
        }
        pushEvent({
          kind: "window_open",
          url: sanitizeUrl(privateLocator),
          target: clip(target || "", 48)
        });
        return null;
      };
      state.windowOpenPatched = true;
    } catch {
      state.windowOpenPatched = false;
    }

    if (state.originalCreateObjectURL) {
      try {
        URL.createObjectURL = function(value) {
          const result = state.originalCreateObjectURL.call(URL, value);
          pushEvent({
            kind: "object_url_created",
            url: sanitizeUrl(result),
            blobType: clip(value?.type || "", 120),
            blobSize: Number.isFinite(value?.size)
              ? Number(value.size)
              : null
          });
          return result;
        };
        state.objectUrlPatched = true;
      } catch {
        state.objectUrlPatched = false;
      }
    }

    window[key] = state;
    return {
      installed: true,
      windowOpenPatched: state.windowOpenPatched,
      objectUrlPatched: state.objectUrlPatched
    };
  })()`;
}

function _cwaGeminiNotebookReadDownloadSinkProbeExpression() {
  return `(() => {
    const state =
      window["__cwaGeminiNotebookDownloadSinkProbeV1"] || null;
    if (!state?.installed) {
      return { installed: false, events: [] };
    }
    return {
      installed: true,
      events: Array.isArray(state.events)
        ? state.events.slice(0, 12)
        : []
    };
  })()`;
}

function _cwaGeminiNotebookRestoreDownloadSinkProbeExpression() {
  return `(() => {
    const key = "__cwaGeminiNotebookDownloadSinkProbeV1";
    const state = window[key] || null;
    if (!state?.installed) return { restored: false };

    try {
      document.removeEventListener("click", state.onClick, true);
    } catch {}
    try {
      document.removeEventListener("submit", state.onSubmit, true);
    } catch {}
    if (state.windowOpenPatched) {
      try {
        window.open = state.originalWindowOpen;
      } catch {}
    }
    if (state.objectUrlPatched && state.originalCreateObjectURL) {
      try {
        URL.createObjectURL = state.originalCreateObjectURL;
      } catch {}
    }
    try {
      delete window[key];
    } catch {
      window[key] = null;
    }
    return { restored: true };
  })()`;
}


function _cwaGeminiNotebookTakeUniqueWindowOpenLocatorExpression() {
  return `(() => {
    const state =
      window["__cwaGeminiNotebookDownloadSinkProbeV1"] || null;
    if (!state?.installed) {
      return { resolved: false, reason: "SINK_PROBE_NOT_INSTALLED" };
    }
    const events = Array.isArray(state.events) ? state.events : [];
    const windowOpenEvents = events.filter(
      (event) => event?.kind === "window_open"
    );
    const locators = Array.isArray(state.privateWindowOpenLocators)
      ? state.privateWindowOpenLocators
      : [];
    if (windowOpenEvents.length !== 1 || locators.length !== 1) {
      return {
        resolved: false,
        reason: "WINDOW_OPEN_LOCATOR_IDENTITY_UNRESOLVED",
        eventCount: windowOpenEvents.length,
        locatorCount: locators.length
      };
    }
    const locator = String(locators[0] || "");
    state.privateWindowOpenLocators = [];
    return {
      resolved: Boolean(locator),
      locator
    };
  })()`;
}

function _cwaGeminiNotebookAudioLocatorPolicy(value) {
  const raw = typeof value === "string" ? value.trim() : "";
  if (!raw) {
    throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_LOCATOR_REQUIRED");
  }
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_LOCATOR_INVALID");
  }
  const hostname = String(parsed.hostname || "").toLowerCase();
  const googleusercontent =
    hostname === "googleusercontent.com" ||
    hostname.endsWith(".googleusercontent.com");
  if (
    parsed.protocol !== "https:" ||
    !googleusercontent ||
    parsed.username ||
    parsed.password ||
    parsed.hash ||
    (parsed.port && parsed.port !== "443")
  ) {
    throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_LOCATOR_REJECTED");
  }
  return {
    locator: parsed.toString(),
    originClass: "GOOGLEUSERCONTENT"
  };
}

function _cwaGeminiNotebookDecodeIoBytes(data, base64Encoded) {
  const text = String(data || "");
  if (base64Encoded === true) {
    const binary = atob(text);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }
  return new TextEncoder().encode(text);
}

function _cwaGeminiNotebookBytesToBase64(bytes) {
  let result = "";
  const blockBytes = 24_576;
  for (let offset = 0; offset < bytes.length; offset += blockBytes) {
    const block = bytes.subarray(offset, offset + blockBytes);
    let binary = "";
    for (let index = 0; index < block.length; index += 1) {
      binary += String.fromCharCode(block[index]);
    }
    result += btoa(binary);
  }
  return result;
}

async function _cwaGeminiNotebookLoadLocatorBytes(
  debuggee,
  locator,
  maxBytes
) {
  let streamHandle = null;

  const headerValue = (headers, name) => {
    if (!headers || typeof headers !== "object") return "";
    const wanted = String(name || "").toLowerCase();
    for (const [key, value] of Object.entries(headers)) {
      if (String(key || "").toLowerCase() === wanted) {
        return String(value || "");
      }
    }
    return "";
  };

  const frameTree = await _cwaBaseSendCommand(
    debuggee,
    "Page.getFrameTree"
  );
  const frameId =
    typeof frameTree?.frameTree?.frame?.id === "string" &&
    frameTree.frameTree.frame.id
      ? frameTree.frameTree.frame.id
      : null;
  if (!frameId) {
    throw new Error(
      "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_FRAME_ID_UNRESOLVED"
    );
  }

  const loaded = await _cwaBaseSendCommand(
    debuggee,
    "Network.loadNetworkResource",
    {
      frameId,
      url: locator,
      options: {
        disableCache: true,
        includeCredentials: true
      }
    }
  );
  const resource =
    loaded?.resource && typeof loaded.resource === "object"
      ? loaded.resource
      : null;
  if (!resource || resource.success !== true) {
    throw new Error(
      "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_NETWORK_RESOURCE_LOAD_FAILED:" +
        String(resource?.netErrorName || resource?.netError || "UNKNOWN")
    );
  }

  const status = Number.isFinite(resource?.httpStatusCode)
    ? Number(resource.httpStatusCode)
    : null;
  if (status === null || status < 200 || status >= 300) {
    throw new Error(
      "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_LOCATOR_RESPONSE_STATUS_INVALID"
    );
  }

  const headers =
    resource?.headers && typeof resource.headers === "object"
      ? resource.headers
      : {};
  const contentType = headerValue(headers, "content-type");
  const normalizedContentType = String(contentType || "")
    .split(";")[0]
    .trim()
    .toLowerCase();
  const mediaLike =
    normalizedContentType.startsWith("audio/") ||
    normalizedContentType === "application/octet-stream" ||
    normalizedContentType === "binary/octet-stream";
  if (!mediaLike) {
    throw new Error(
      "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_LOCATOR_MEDIA_TYPE_UNPROVEN:" +
        normalizedContentType
    );
  }

  const contentLengthText = headerValue(
    headers,
    "content-length"
  ).trim();
  const contentLength = /^\d+$/.test(contentLengthText)
    ? Number(contentLengthText)
    : null;
  if (
    Number.isFinite(contentLength) &&
    contentLength !== null &&
    contentLength > maxBytes
  ) {
    throw new Error(
      "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_LIMIT_EXCEEDED"
    );
  }

  streamHandle =
    typeof resource?.stream === "string" && resource.stream
      ? resource.stream
      : null;
  if (!streamHandle) {
    throw new Error(
      "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_RESPONSE_STREAM_MISSING"
    );
  }

  try {
    const chunks = [];
    let totalBytes = 0;
    while (true) {
      const part = await _cwaBaseSendCommand(debuggee, "IO.read", {
        handle: streamHandle,
        size: 262_144
      });
      const bytes = _cwaGeminiNotebookDecodeIoBytes(
        part?.data,
        part?.base64Encoded === true
      );
      totalBytes += bytes.length;
      if (totalBytes > maxBytes) {
        throw new Error(
          "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_LIMIT_EXCEEDED"
        );
      }
      if (bytes.length > 0) chunks.push(bytes);
      if (part?.eof === true) break;
    }

    const combined = new Uint8Array(totalBytes);
    let cursor = 0;
    for (const chunk of chunks) {
      combined.set(chunk, cursor);
      cursor += chunk.length;
    }

    const digestBytes = new Uint8Array(
      await crypto.subtle.digest("SHA-256", combined)
    );
    const sha256 = Array.from(
      digestBytes,
      (value) => value.toString(16).padStart(2, "0")
    ).join("");
    const bodyBase64 = _cwaGeminiNotebookBytesToBase64(combined);

    return {
      responseStatusCode: status,
      contentType: String(contentType || "").slice(0, 160),
      normalizedContentType,
      contentDispositionPresent: Boolean(
        headerValue(headers, "content-disposition")
      ),
      totalBytes,
      sha256,
      bodyBase64,
      networkResourceLoadProven: true
    };
  } finally {
    if (streamHandle) {
      try {
        await _cwaBaseSendCommand(debuggee, "IO.close", {
          handle: streamHandle
        });
      } catch {}
    }
  }
}

async function _cwaGeminiNotebookProbeAudioArtifactBytes(message, port) {
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

  const maxBytes = Math.max(
    1,
    Math.min(
      Number(message?.maxBytes) || 67_108_864,
      67_108_864
    )
  );
  const timeoutMs = Math.max(
    5000,
    Math.min(Number(message?.timeoutMs) || 120000, 180000)
  );
  const startedAt = performance.now();
  const deadlineAt = startedAt + timeoutMs;
  const tab = await _cwaGeminiNotebookFindExactOpenTab(notebookUrl);
  const debuggee = { tabId: tab.id };
  let attached = false;
  let sinkProbeInstalled = false;
  let downloadAttemptMayHaveExecuted = false;

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const beforeMenus = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookVisibleArtifactMenusExpression()
    );
    const beforePanels = Array.isArray(beforeMenus?.panels)
      ? beforeMenus.panels
      : [];
    if (beforePanels.length !== 0) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PRESTATE_MENU_OPEN:" +
          String(beforePanels.length)
      );
    }

    const opened = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookClickExactArtifactMoreMenuExpression(
        expectedArtifactRef
      )
    );
    if (opened?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_CLICK_FAILED:" +
          String(opened?.reason || "UNKNOWN")
      );
    }

    let menu = null;
    while (performance.now() < deadlineAt) {
      const state = await _cwaGeminiNotebookMutationEvaluate(
        debuggee,
        _cwaGeminiNotebookVisibleArtifactMenusExpression()
      );
      const panels = Array.isArray(state?.panels) ? state.panels : [];
      if (panels.length > 1) {
        throw new Error(
          "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_IDENTITY_AMBIGUOUS:" +
            String(panels.length)
        );
      }
      if (panels.length === 1) {
        menu = panels[0];
        break;
      }
      await sleep(100);
    }
    if (!menu) {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_TIMEOUT");
    }

    const downloadCandidates = Array.isArray(menu?.items)
      ? menu.items.filter(
          (item) =>
            item?.tag === "button" &&
            item?.role === "menuitem" &&
            item?.disabled === false &&
            String(item?.className || "").includes("mat-mdc-menu-item") &&
            Array.isArray(item?.icons) &&
            item.icons.includes("save_alt")
        )
      : [];
    if (downloadCandidates.length !== 1) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_ACTION_IDENTITY_UNRESOLVED:" +
          String(downloadCandidates.length)
      );
    }

    const sinkInstall = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookInstallDownloadSinkProbeExpression()
    );
    if (
      sinkInstall?.installed !== true ||
      sinkInstall?.windowOpenPatched !== true
    ) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_SINK_PROBE_INSTALL_FAILED"
      );
    }
    sinkProbeInstalled = true;

    downloadAttemptMayHaveExecuted = true;
    const clicked = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookClickVisibleArtifactDownloadExpression()
    );
    if (clicked?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_CLICK_FAILED:" +
          String(clicked?.reason || "UNKNOWN")
      );
    }

    let sinkState = { installed: true, events: [] };
    while (performance.now() < deadlineAt) {
      sinkState = await _cwaGeminiNotebookMutationEvaluate(
        debuggee,
        _cwaGeminiNotebookReadDownloadSinkProbeExpression()
      );
      const events = Array.isArray(sinkState?.events)
        ? sinkState.events
        : [];
      if (events.some((event) => event?.kind === "window_open")) break;
      await sleep(50);
    }

    const locatorState = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookTakeUniqueWindowOpenLocatorExpression()
    );
    if (locatorState?.resolved !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_WINDOW_OPEN_LOCATOR_UNRESOLVED:" +
          String(locatorState?.reason || "UNKNOWN")
      );
    }

    const policy = _cwaGeminiNotebookAudioLocatorPolicy(
      locatorState.locator
    );

    const acquired = await _cwaGeminiNotebookLoadLocatorBytes(
      debuggee,
      policy.locator,
      maxBytes
    );

    const bodyBase64 = acquired.bodyBase64;
    if (
      typeof bodyBase64 !== "string" ||
      !/^[0-9a-f]{64}$/.test(acquired.sha256 || "")
    ) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_TRANSFER_SOURCE_INVALID"
      );
    }
    const chunkCount = Math.max(
      1,
      Math.ceil(
        bodyBase64.length /
          CWA_GEMINI_NOTEBOOK_AUDIO_BYTE_CHUNK_BASE64_CHARS
      )
    );

    for (let chunkIndex = 0; chunkIndex < chunkCount; chunkIndex += 1) {
      const data = bodyBase64.slice(
        chunkIndex *
          CWA_GEMINI_NOTEBOOK_AUDIO_BYTE_CHUNK_BASE64_CHARS,
        (chunkIndex + 1) *
          CWA_GEMINI_NOTEBOOK_AUDIO_BYTE_CHUNK_BASE64_CHARS
      );
      if (
        !safePortPost(port, {
          protocol: BRIDGE_PROTOCOL_VERSION,
          type: CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_CHUNK_TYPE,
          request_id: message.request_id,
          chunkIndex,
          chunkCount,
          totalBytes: acquired.totalBytes,
          sha256: acquired.sha256,
          data
        })
      ) {
        throw new Error(
          "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_CHUNK_DELIVERY_FAILED"
        );
      }
    }

    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      notebookUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      observedArtifactRef: expectedArtifactRef,
      locatorOriginClass: policy.originClass,
      responseStatusCode: acquired.responseStatusCode,
      contentType: acquired.contentType,
      normalizedContentType: acquired.normalizedContentType,
      contentDispositionPresent: acquired.contentDispositionPresent,
      totalBytes: acquired.totalBytes,
      sha256: acquired.sha256,
      chunkCount,
      browserBytesProven: true,
      networkResourceLoadProven:
        acquired.networkResourceLoadProven === true,
      authenticatedBrowserRequestProven: true,
      acquisitionTabCreated: false,
      rawDownloadUrlExported: false,
      privateProtocolBodyRead: false,
      finalDestinationWritten: false,
      automaticRetry: false
    };
  } catch (error) {
    if (downloadAttemptMayHaveExecuted) {
      throw _cwaGeminiNotebookAmbiguousError(error);
    }
    throw error;
  } finally {
    if (sinkProbeInstalled && attached) {
      try {
        await _cwaGeminiNotebookMutationEvaluate(
          debuggee,
          _cwaGeminiNotebookRestoreDownloadSinkProbeExpression()
        );
      } catch {}
    }
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {}
    }
  }
}

async function _cwaGeminiNotebookProbeAudioArtifactDownloadIntent(message) {
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

  const timeoutMs = Math.max(
    3000,
    Math.min(Number(message?.timeoutMs) || 15000, 30000)
  );
  const startedAt = performance.now();
  const deadlineAt = startedAt + timeoutMs;
  const tab = await _cwaGeminiNotebookFindExactOpenTab(notebookUrl);
  const debuggee = { tabId: tab.id };
  let attached = false;
  let listenerInstalled = false;
  let fetchEnabled = false;
  let sinkProbeInstalled = false;
  let downloadAttemptMayHaveExecuted = false;
  const observedResponses = [];
  const payloadCandidates = [];
  const pendingHandlers = new Set();

  const responseHeader = (params, name) => {
    const wanted = String(name || "").toLowerCase();
    const headers = Array.isArray(params?.responseHeaders)
      ? params.responseHeaders
      : [];
    return headers
      .filter(
        (header) =>
          String(header?.name || "").toLowerCase() === wanted
      )
      .map((header) => String(header?.value || ""))
      .join("\n");
  };

  const sanitizeUrl = (value) => {
    try {
      const parsed = new URL(String(value || ""));
      return {
        origin: parsed.origin,
        hasQuery: Boolean(parsed.search),
        pathSuffix: String(parsed.pathname || "")
          .split("/")
          .filter(Boolean)
          .slice(-2)
      };
    } catch {
      return { origin: "", hasQuery: false, pathSuffix: [] };
    }
  };

  const continuePaused = async (requestId) => {
    try {
      await _cwaBaseSendCommand(debuggee, "Fetch.continueResponse", {
        requestId
      });
    } catch {
      await _cwaBaseSendCommand(debuggee, "Fetch.continueRequest", {
        requestId
      });
    }
  };

  const handlePaused = async (params) => {
    const requestId = String(params?.requestId || "");
    if (!requestId) return;

    if (!downloadAttemptMayHaveExecuted) {
      await continuePaused(requestId);
      return;
    }

    const contentDisposition = responseHeader(params, "content-disposition");
    const contentType = responseHeader(params, "content-type");
    const normalizedContentType = String(contentType || "")
      .split(";")[0]
      .trim()
      .toLowerCase();
    const attachmentLike = /attachment/i.test(contentDisposition);
    const url = sanitizeUrl(params?.request?.url || "");
    const jsonLike =
      normalizedContentType === "application/json" ||
      normalizedContentType.endsWith("+json");
    const controlPlaneLikely =
      jsonLike &&
      attachmentLike &&
      String(params?.resourceType || "") === "XHR";
    const mediaLike =
      normalizedContentType.startsWith("audio/") ||
      normalizedContentType === "application/octet-stream" ||
      normalizedContentType === "binary/octet-stream";
    const payloadCandidate =
      !controlPlaneLikely && (mediaLike || attachmentLike);

    const summary = {
      requestId,
      responseStatusCode: Number.isFinite(params?.responseStatusCode)
        ? Number(params.responseStatusCode)
        : null,
      resourceType: String(params?.resourceType || ""),
      contentDispositionPresent: Boolean(contentDisposition),
      contentDispositionAttachment: attachmentLike,
      contentType: String(contentType || "").slice(0, 160),
      normalizedContentType,
      urlOrigin: url.origin,
      urlHasQuery: url.hasQuery,
      urlPathSuffix: url.pathSuffix,
      controlPlaneLikely,
      payloadCandidate,
      blocked: payloadCandidate
    };
    if (observedResponses.length < 16) {
      observedResponses.push(summary);
    }

    if (!payloadCandidate) {
      await continuePaused(requestId);
      return;
    }

    payloadCandidates.push(summary);
    try {
      await _cwaBaseSendCommand(debuggee, "Fetch.failRequest", {
        requestId,
        errorReason: "Aborted"
      });
    } catch {
      // Outer ambiguity handling forbids retry after the effect boundary.
    }
  };

  const observer = (source, method, params) => {
    if (source?.tabId !== tab.id || method !== "Fetch.requestPaused") return;
    const promise = handlePaused(params);
    pendingHandlers.add(promise);
    void promise.finally(() => pendingHandlers.delete(promise));
  };

  try {
    await chrome.debugger.attach(debuggee, CDP_PROTOCOL_VERSION);
    attached = true;
    await _cwaBaseSendCommand(debuggee, "Runtime.enable");

    const beforeMenus = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookVisibleArtifactMenusExpression()
    );
    const beforePanels = Array.isArray(beforeMenus?.panels)
      ? beforeMenus.panels
      : [];
    if (beforePanels.length !== 0) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_PRESTATE_MENU_OPEN:" +
          String(beforePanels.length)
      );
    }

    const opened = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookClickExactArtifactMoreMenuExpression(
        expectedArtifactRef
      )
    );
    if (opened?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_CLICK_FAILED:" +
          String(opened?.reason || "UNKNOWN")
      );
    }

    let menu = null;
    while (performance.now() < deadlineAt) {
      const state = await _cwaGeminiNotebookMutationEvaluate(
        debuggee,
        _cwaGeminiNotebookVisibleArtifactMenusExpression()
      );
      const panels = Array.isArray(state?.panels) ? state.panels : [];
      if (panels.length > 1) {
        throw new Error(
          "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_IDENTITY_AMBIGUOUS:" +
            String(panels.length)
        );
      }
      if (panels.length === 1) {
        menu = panels[0];
        break;
      }
      await sleep(100);
    }
    if (!menu) {
      throw new Error("GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_TIMEOUT");
    }

    const downloadCandidates = Array.isArray(menu?.items)
      ? menu.items.filter(
          (item) =>
            item?.tag === "button" &&
            item?.role === "menuitem" &&
            item?.disabled === false &&
            String(item?.className || "").includes("mat-mdc-menu-item") &&
            Array.isArray(item?.icons) &&
            item.icons.includes("save_alt")
        )
      : [];
    if (downloadCandidates.length !== 1) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_ACTION_IDENTITY_UNRESOLVED:" +
          String(downloadCandidates.length)
      );
    }

    const sinkInstall = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookInstallDownloadSinkProbeExpression()
    );
    if (sinkInstall?.installed !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_SINK_PROBE_INSTALL_FAILED"
      );
    }
    sinkProbeInstalled = true;

    chrome.debugger.onEvent.addListener(observer);
    listenerInstalled = true;
    await _cwaBaseSendCommand(debuggee, "Fetch.enable", {
      patterns: [{ urlPattern: "*", requestStage: "Response" }]
    });
    fetchEnabled = true;

    downloadAttemptMayHaveExecuted = true;
    const clicked = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookClickVisibleArtifactDownloadExpression()
    );
    if (clicked?.clicked !== true) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_CLICK_FAILED:" +
          String(clicked?.reason || "UNKNOWN")
      );
    }

    let sinkState = { installed: true, events: [] };
    while (performance.now() < deadlineAt) {
      sinkState = await _cwaGeminiNotebookMutationEvaluate(
        debuggee,
        _cwaGeminiNotebookReadDownloadSinkProbeExpression()
      );
      const sinkEvents = Array.isArray(sinkState?.events)
        ? sinkState.events
        : [];
      if (payloadCandidates.length > 0 || sinkEvents.length > 0) break;
      await sleep(50);
    }

    await Promise.allSettled(Array.from(pendingHandlers));

    sinkState = await _cwaGeminiNotebookMutationEvaluate(
      debuggee,
      _cwaGeminiNotebookReadDownloadSinkProbeExpression()
    );
    const sinkEvents = Array.isArray(sinkState?.events)
      ? sinkState.events
      : [];

    if (payloadCandidates.length > 1) {
      throw new Error(
        "GEMINI_NOTEBOOK_AUDIO_ARTIFACT_PAYLOAD_RESPONSE_AMBIGUOUS:" +
          String(payloadCandidates.length)
      );
    }

    const candidate =
      payloadCandidates.length === 1 ? payloadCandidates[0] : null;

    return {
      productId: CWA_GEMINI_NOTEBOOK_PRODUCT_ID,
      notebookUrl,
      tabId: tab.id,
      elapsedMs: Math.round(performance.now() - startedAt),
      observedArtifactRef: expectedArtifactRef,
      downloadAttemptMayHaveExecuted: true,
      downloadClickPerformed: true,
      payloadResponseObserved: candidate !== null,
      fetchRequestId: candidate ? candidate.requestId : "",
      responseStatusCode: candidate
        ? candidate.responseStatusCode
        : null,
      resourceType: candidate ? candidate.resourceType : "",
      contentDispositionPresent: candidate
        ? candidate.contentDispositionPresent
        : false,
      contentDispositionAttachment: candidate
        ? candidate.contentDispositionAttachment
        : false,
      contentType: candidate ? candidate.contentType : "",
      normalizedContentType: candidate
        ? candidate.normalizedContentType
        : "",
      downloadUrlOrigin: candidate ? candidate.urlOrigin : "",
      downloadUrlHasQuery: candidate ? candidate.urlHasQuery : false,
      downloadUrlPathSuffix: candidate ? candidate.urlPathSuffix : [],
      observedResponses,
      downloadSinkObserved: sinkEvents.length > 0,
      downloadSinkEvents: sinkEvents,
      downloadSinkWindowOpenPatched: sinkInstall.windowOpenPatched === true,
      downloadSinkObjectUrlPatched: sinkInstall.objectUrlPatched === true,
      responseBlockedBeforeBody: candidate !== null,
      responseBodyRead: false,
      filesystemArtifactProven: false,
      productWritePerformed: false,
      navigationPerformed: false,
      automaticRetry: false,
      rawDownloadUrlExported: false
    };
  } catch (error) {
    if (downloadAttemptMayHaveExecuted) {
      throw _cwaGeminiNotebookAmbiguousError(error);
    }
    throw error;
  } finally {
    if (sinkProbeInstalled && attached) {
      try {
        await _cwaGeminiNotebookMutationEvaluate(
          debuggee,
          _cwaGeminiNotebookRestoreDownloadSinkProbeExpression()
        );
      } catch {
        // Probe cleanup cannot grant retry authority.
      }
    }
    if (fetchEnabled) {
      try {
        await _cwaBaseSendCommand(debuggee, "Fetch.disable");
      } catch {
        // Cleanup cannot grant retry authority.
      }
    }
    if (listenerInstalled) {
      try {
        chrome.debugger.onEvent.removeListener(observer);
      } catch {
        // Listener cleanup cannot change the already-classified outcome.
      }
    }
    if (attached) {
      try {
        await chrome.debugger.detach(debuggee);
      } catch {
        // Detach cannot change the already-classified download intent.
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
      CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_OPERATION,
      CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PROBE_OPERATION,
      CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_INTENT_PROBE_OPERATION,
      CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROBE_OPERATION,
      CWA_GEMINI_NOTEBOOK_STUDIO_CREATION_CONTROLS_PROBE_OPERATION,
      CWA_GEMINI_NOTEBOOK_VIDEO_CONFIG_PROBE_OPERATION,
      CWA_GEMINI_NOTEBOOK_VIDEO_GENERATION_PROBE_OPERATION,
      CWA_GEMINI_NOTEBOOK_VIDEO_ARTIFACT_OBSERVE_PROBE_OPERATION
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
          : operation === CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PROBE_OPERATION
            ? "gemini_notebook_audio_artifact_menu_probe_result"
            : operation === CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_INTENT_PROBE_OPERATION
              ? "gemini_notebook_audio_artifact_download_intent_probe_result"
              : operation === CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROBE_OPERATION
                ? "gemini_notebook_audio_artifact_byte_probe_result"
                : operation === CWA_GEMINI_NOTEBOOK_STUDIO_CREATION_CONTROLS_PROBE_OPERATION
                  ? "gemini_notebook_studio_creation_controls_probe_result"
                  : operation === CWA_GEMINI_NOTEBOOK_VIDEO_CONFIG_PROBE_OPERATION
                    ? "gemini_notebook_video_config_probe_result"
                    : operation === CWA_GEMINI_NOTEBOOK_VIDEO_GENERATION_PROBE_OPERATION
                      ? "gemini_notebook_video_generation_probe_result"
                      : operation === CWA_GEMINI_NOTEBOOK_VIDEO_ARTIFACT_OBSERVE_PROBE_OPERATION
                        ? "gemini_notebook_video_artifact_observe_probe_result"
                        : "gemini_notebook_add_url_source_result";

  try {
    const result =
      operation === CWA_GEMINI_NOTEBOOK_GENERATE_AUDIO_OVERVIEW_OPERATION
        ? await _cwaGeminiNotebookGenerateAudioOverview(message)
        : operation === CWA_GEMINI_NOTEBOOK_OBSERVE_AUDIO_OVERVIEW_OPERATION
          ? await _cwaGeminiNotebookObserveAudioOverview(message)
          : operation === CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_ACTION_PROBE_OPERATION
            ? await _cwaGeminiNotebookProbeAudioArtifactAction(message)
            : operation === CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_MENU_PROBE_OPERATION
              ? await _cwaGeminiNotebookProbeAudioArtifactMenu(message)
              : operation === CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_DOWNLOAD_INTENT_PROBE_OPERATION
                ? await _cwaGeminiNotebookProbeAudioArtifactDownloadIntent(message)
                : operation === CWA_GEMINI_NOTEBOOK_AUDIO_ARTIFACT_BYTE_PROBE_OPERATION
                  ? await _cwaGeminiNotebookProbeAudioArtifactBytes(message, port)
                  : operation === CWA_GEMINI_NOTEBOOK_STUDIO_CREATION_CONTROLS_PROBE_OPERATION
                    ? await _cwaGeminiNotebookProbeStudioCreationControls(message)
                    : operation === CWA_GEMINI_NOTEBOOK_VIDEO_CONFIG_PROBE_OPERATION
                      ? await _cwaGeminiNotebookProbeVideoConfig(message)
                      : operation === CWA_GEMINI_NOTEBOOK_VIDEO_GENERATION_PROBE_OPERATION
                        ? await _cwaGeminiNotebookProbeVideoGeneration(message)
                        : operation === CWA_GEMINI_NOTEBOOK_VIDEO_ARTIFACT_OBSERVE_PROBE_OPERATION
                          ? await _cwaGeminiNotebookProbeVideoArtifactObservation(message)
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
