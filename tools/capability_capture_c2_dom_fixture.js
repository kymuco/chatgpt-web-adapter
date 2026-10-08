// Synthetic CDP/page exercise for C2. Nothing touches a real browser.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const workerPath = path.join(
  __dirname, "..", "src", "chatgpt_web_adapter", "browser_native_extension",
  "service_worker_capability_capture_c2.js"
);
const worker = vm.createContext({
  URL,
  performance,
  setTimeout,
  BRIDGE_PROTOCOL_VERSION: "synthetic",
  CDP_PROTOCOL_VERSION: "1.3",
  sleep: ms => new Promise(resolve => setTimeout(resolve, ms))
});
vm.runInContext(fs.readFileSync(workerPath, "utf8"), worker);

class FakeElement {
  constructor(tag, left, { parent = null } = {}) {
    this.tagName = tag.toUpperCase();
    this.left = left;
    this.parentElement = parent;
    this.children = [];
    this.isConnected = true;
    this.isContentEditable = false;
    this.hiddenInFixture = false;
    if (parent) parent.children.push(this);
  }
  getBoundingClientRect() {
    return { left: this.left, width: 100, height: 35 };
  }
  contains(element) {
    for (let current = element; current; current = current.parentElement) {
      if (this === current) return true;
    }
    return false;
  }
}

function makePage(tabId) {
  const root = new FakeElement("html", 0);
  const source = new FakeElement("textarea", 100, { parent: root });
  const result = new FakeElement("span", 750, { parent: root });
  let inputListener = null;
  let activeObserver = null;
  class FakeMutationObserver {
    constructor(fn) { this.fn = fn; }
    observe() { activeObserver = this; }
    disconnect() {
      if (activeObserver === this) activeObserver = null;
    }
  }
  const document = {
    documentElement: Object.assign(root, { clientWidth: 1000 }),
    addEventListener(name, callback, capture) {
      assert.equal(name, "input");
      assert.equal(capture, true);
      inputListener = callback;
    },
    removeEventListener(name, callback, capture) {
      assert.equal(name, "input");
      assert.equal(capture, true);
      assert.equal(inputListener, callback);
      inputListener = null;
    }
  };
  const context = vm.createContext({
    URL, performance, document,
    Element: FakeElement,
    MutationObserver: FakeMutationObserver,
    location: { href: "https://translate.google.com/?sl=en&tl=es&op=translate" },
    getComputedStyle(element) {
      return {
        display: element.hiddenInFixture ? "none" : "block",
        visibility: "visible"
      };
    }
  });
  return {
    tabId, context, root, source, result,
    input(target = source, trusted = true) {
      assert.ok(inputListener);
      inputListener({ target, isTrusted: trusted, data: "sensitive source value" });
    },
    changed(node = result) {
      assert.ok(activeObserver);
      const rawNode = { parentElement: node, data: "sensitive result value" };
      activeObserver.fn([{ type: "characterData", target: rawNode }]);
    },
    listenerActive() { return inputListener !== null; },
    observerActive() { return activeObserver !== null; }
  };
}

const pages = new Map();
const page = makePage(1001);
pages.set(1001, page);
let attachCount = 0;
let detachCount = 0;
let lostDetach = false;
let productWrites = 0;
worker.chrome = {
  tabs: {
    async get(id) {
      if (!pages.has(id)) throw new Error("not found");
      return {
        id, url: "https://translate.google.com/?sl=en&tl=es&op=translate"
      };
    }
  },
  debugger: {
    async attach() { attachCount++; },
    async detach() {
      detachCount++;
      if (lostDetach) throw new Error("lost detach");
    }
  }
};
worker._cwaBaseSendCommand = async (debuggee, operation, args) => {
  if (operation === "Runtime.enable") return {};
  assert.equal(operation, "Runtime.evaluate");
  assert.ok(!("userGesture" in args));
  return {
    result: {
      value: vm.runInContext(args.expression, pages.get(debuggee.tabId).context)
    }
  };
};
worker.safePortPost = () => { throw new Error("unexpected post"); };

const request = {
  tabId: 1001,
  sourceLanguage: "en",
  targetLanguage: "es",
  seconds: 6,
  consent: "EXPLICIT_SINGLE_TAB_EVENT_DELTA"
};
const expr = action => worker._cwaC2Expression(action, "en", "es");
function evalPage(action) { return vm.runInContext(expr(action), page.context); }

async function run() {
  const sourceText = fs.readFileSync(workerPath, "utf8");
  const pageProbe = sourceText.split("function _cwaC2PageProbe(", 2)[1]
    .split("function _cwaC2Expression(", 1)[0];
  const banned = [
    "querySelectorAll", "querySelector(", "jsname", "W297wb", "jqKxS",
    ".textContent", ".innerText", ".outerHTML", ".value", ".data",
    "localStorage", "fetch(", "XMLHttpRequest", "chrome.tabs.update",
    "chrome.tabs.create"
  ];
  for (const item of banned) {
    assert.equal(pageProbe.includes(item), false, "forbidden: " + item);
  }

  // Source event, changed text node and cleanup work without output values.
  assert.equal(evalPage("install").installed, true);
  page.input(page.source, false);
  assert.equal(evalPage("observe").inputEvents, 0);
  const unsupported = new FakeElement("div", 320, { parent: page.root });
  const hidden = new FakeElement("textarea", 360, { parent: page.root });
  hidden.hiddenInFixture = true;
  page.input(unsupported);
  page.input(hidden);
  assert.equal(evalPage("observe").sourceCandidateCount, 0);
  page.input();
  page.changed();
  let sample = evalPage("observe");
  assert.equal(sample.sourceCandidateCount, 1);
  assert.equal(sample.inputFilterCounts.observed, 4);
  assert.equal(sample.inputFilterCounts.trusted, 3);
  assert.equal(sample.inputFilterCounts.eligible, 1);
  assert.equal(sample.inputFilterCounts.unsupportedTarget, 1);
  assert.equal(sample.inputFilterCounts.invisibleTarget, 1);
  assert.ok(sample.observerWindowMs >= 0 && sample.observerWindowMs <= 20000);
  assert.equal(sample.sourceDescriptor.kind, "textarea");
  assert.equal(sample.mutationLeafCount, 1);
  assert.equal(sample.mutationLeafDescriptor.kind, "span");
  assert.equal(sample.structuralQuiet, false);
  assert.equal(JSON.stringify(sample).includes("sensitive"), false);
  await new Promise(resolve => setTimeout(resolve, 1100));
  sample = evalPage("observe");
  assert.equal(sample.structuralQuiet, true);
  assert.equal(worker._cwaC2ValidateSample(sample).mutationLeafCount, 1);
  assert.equal(evalPage("remove").removed, true);
  assert.equal(page.listenerActive(), false);
  assert.equal(page.observerActive(), false);

  // Distinct input targets make the source ambiguous, not leftmost.
  assert.equal(evalPage("install").installed, true);
  const otherInput = new FakeElement("input", 280, { parent: page.root });
  page.input();
  page.input(otherInput);
  sample = evalPage("observe");
  assert.equal(sample.sourceCandidateCount, 2);
  assert.equal(sample.sourceDescriptor, null);
  assert.equal(sample.sourceAmbiguous, true);
  evalPage("remove");

  // Multiple changed leaves are ambiguous, never guessed by region/order.
  assert.equal(evalPage("install").installed, true);
  page.input();
  page.changed();
  const anotherOutput = new FakeElement("p", 800, { parent: page.root });
  page.changed(anotherOutput);
  sample = evalPage("observe");
  assert.equal(sample.mutationLeafCount, 2);
  assert.equal(sample.mutationLeafDescriptor, null);
  assert.equal(worker._cwaC2ValidateSample(sample).mutationLeafCount, 2);
  evalPage("remove");

  // The event filter must cap raw events as well as accepted events.
  assert.equal(evalPage("install").installed, true);
  for (let i = 0; i < 65; i++) page.input(page.source, false);
  sample = evalPage("observe");
  assert.equal(sample.inputFilterCounts.observed, 64);
  assert.equal(sample.inputFilterCounts.trusted, 0);
  assert.equal(sample.mutationOverflow, true);
  evalPage("remove");

  // Public worker capture path: caller manually triggers event after install.
  setTimeout(() => page.input(), 75);
  setTimeout(() => page.changed(), 150);
  const success = await worker._cwaC2ObserveReferenceIndependentDelta(request);
  assert.equal(success.schema, "CWA_CAPTURE_C2_INDEPENDENT_DELTA_V1");
  assert.equal(success.inputFilterCounts.observed, 1);
  assert.equal(success.inputFilterCounts.trusted, 1);
  assert.equal(success.inputFilterCounts.eligible, 1);
  assert.ok(success.observerWindowMs > 0);
  assert.equal(success.source.status, "EVENT_TARGET_OBSERVED");
  assert.equal(success.result.status, "ONE_STRUCTURAL_CHANGE_CANDIDATE");
  assert.equal(success.referenceSelectorConsulted, false);
  assert.equal(success.learnedLocatorProven, false);
  assert.equal(success.replayExecutable, false);
  assert.equal(success.newWriteAuthority, false);
  assert.equal(success.semanticFinalityProven, false);
  assert.equal(success.rawContentRetained, false);
  assert.equal(attachCount, 1);
  assert.equal(detachCount, 1);
  assert.equal(page.listenerActive(), false);
  assert.equal(page.observerActive(), false);
  assert.equal(productWrites, 0);

  // Preflight refuses bad route, missing consent and bad duration.
  await assert.rejects(
    () => worker._cwaC2ObserveReferenceIndependentDelta({
      ...request, consent: "none"
    }),
    /CAPTURE_C2_CONSENT_REQUIRED/
  );
  await assert.rejects(
    () => worker._cwaC2ObserveReferenceIndependentDelta({
      ...request, seconds: 120
    }),
    /CAPTURE_C2_INVALID_REQUEST/
  );

  // Even cleanup ambiguity produces explicit failure, not success.
  lostDetach = true;
  setTimeout(() => page.input(), 75);
  setTimeout(() => page.changed(), 150);
  await assert.rejects(
    () => worker._cwaC2ObserveReferenceIndependentDelta(request),
    /CAPTURE_C2_CLEANUP_UNPROVEN/
  );
  assert.equal(attachCount, 2);
  assert.equal(detachCount, 2);

  // Test integration through the outer handwritten Translate router.
  worker.importScripts = script => {
    assert.ok([
      "service_worker_capability_capture_v0.js",
      "service_worker_capability_capture_c2.js"
    ].includes(script));
  };
  const gtPath = path.join(
    __dirname, "..", "src", "chatgpt_web_adapter",
    "browser_native_extension", "service_worker_google_translate_capability.js"
  );
  vm.runInContext(fs.readFileSync(gtPath, "utf8"), worker);
  const routed = [];
  worker._cwaOnNativeMessageWithIndependentDelta = async msg =>
    routed.push(msg.type);
  await worker._cwaOnNativeMessageWithGoogleTranslate(
    { type: "research_capture_independent_delta_v0", request_id: "r" },
    {},
    () => { throw new Error("unexpected fallthrough"); }
  );
  assert.deepEqual(routed, ["research_capture_independent_delta_v0"]);

  process.stdout.write("CAPTURE_C2_SYNTHETIC_EVENT_DELTA_OK\n");
}
run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
