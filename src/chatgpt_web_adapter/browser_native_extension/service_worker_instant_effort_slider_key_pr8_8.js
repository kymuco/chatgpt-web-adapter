// PR8.8 semantic Home-key operations for the proven effort slider.

async function _pr88InstantEffortWaitForSlider(debuggee, expectedMode, timeoutMs = 2500) {
  const startedAt = performance.now();
  let last = null;
  while (performance.now() - startedAt < timeoutMs) {
    last = await _pr88InstantEffortSliderSnapshot(debuggee, "snapshot");
    if (
      last?.found === true && last?.candidateCount === 1 &&
      last?.min === 0 && last?.max === 2 && Number.isInteger(last?.now) &&
      last?.stepCount === 3 && last?.currentControlOpen === true &&
      last?.currentMode === expectedMode && last?.disabled !== true &&
      last?.pointerEventsEnabled !== false
    ) return last;
    await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
  }
  return last || {found:false, reason:"effort_slider_timeout", candidateCount:0};
}

async function _pr88InstantEffortDispatchHome(debuggee) {
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type:"rawKeyDown", key:"Home", code:"Home",
    windowsVirtualKeyCode:36, nativeVirtualKeyCode:36
  });
  await chrome.debugger.sendCommand(debuggee, "Input.dispatchKeyEvent", {
    type:"keyUp", key:"Home", code:"Home",
    windowsVirtualKeyCode:36, nativeVirtualKeyCode:36
  });
}

async function _pr88InstantEffortWaitForSelected(debuggee, timeoutMs) {
  const startedAt = performance.now();
  let selected = null;
  let slider = null;
  let sliderMinReached = false;
  let sliderObservedAfterHome = false;
  while (performance.now() - startedAt < timeoutMs) {
    selected = await _pr88InstantSelectedModeSnapshot(debuggee);
    slider = await _pr88InstantEffortSliderSnapshot(debuggee, "snapshot");
    if (slider?.found === true) {
      sliderObservedAfterHome = true;
      if (slider?.min === 0 && slider?.now === slider?.min) sliderMinReached = true;
    }
    if (
      selected?.selectedModeProven === true &&
      selected?.selectedMode === "INSTANT" &&
      (sliderMinReached || slider?.found !== true)
    ) {
      return {selected, slider, sliderMinReached, sliderObservedAfterHome};
    }
    await sleep(PR88_INSTANT_EFFORT_SELECTION_POLL_MS);
  }
  return {selected, slider, sliderMinReached, sliderObservedAfterHome};
}
