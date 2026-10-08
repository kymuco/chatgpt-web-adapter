// C1 synthetic two-document CDP contract; no Chrome connection or product write.
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const worker = vm.createContext({});
const workerPath = path.join(
  __dirname, "..", "src", "chatgpt_web_adapter",
  "browser_native_extension", "service_worker_capability_capture_v0.js"
);
vm.runInContext(fs.readFileSync(workerPath, "utf8"), worker);

class FakeElement {
  constructor(tagName, left, text) {
    this.tagName = tagName;
    this.left = left;
    this.textContent = text;
    this.disabled = false;
    this.hidden = false;
  }
  getBoundingClientRect() {
    return { left: this.left, width: 90, height: 30 };
  }
  getAttribute(name) {
    if (name === "aria-disabled") return null;
    throw new Error("Unexpected attribute read: " + name);
  }
  contains(other) { return this === other; }
}

const pages = new Map();
function page(tab, sourceCount = 1, outputCount = 1, variant = "") {
  const fields = Array.from({ length: sourceCount }, (_, i) =>
    new FakeElement("TEXTAREA", 100 + 90 * i, "secret input " + variant)
  );
  const outputs = Array.from({ length: outputCount }, (_, i) =>
    new FakeElement("SPAN", 800 + 25 * i, "private translation " + variant)
  );
  const ctx = vm.createContext({
    document: {
      documentElement: { clientWidth: 1000 },
      querySelectorAll(selector) {
        if (selector.startsWith("textarea")) return fields;
        if (selector.startsWith("[jsname")) return outputs;
        throw new Error("Unexpected selector");
      }
    },
    location: {
      href: "https://translate.google.com/?sl=en&tl=es&op=translate"
    },
    getComputedStyle(element) {
      return {
        display: element.hidden ? "none" : "block",
        visibility: "visible"
      };
    },
    URL
  });
  pages.set(tab, ctx);
  return { fields, outputs, ctx };
}

const a = page(101, 1, 1, "A");
const b = page(102, 1, 1, "B");
let detachCount = 0;
let failDetach = false;
let attachCount = 0;

worker.chrome = {
  tabs: {
    async get(id) {
      if (!pages.has(id)) throw new Error("missing tab");
      return {
        id,
        url: "https://translate.google.com/?sl=en&tl=es&op=translate"
      };
    }
  },
  debugger: {
    async attach() { attachCount++; },
    async detach() {
      detachCount++;
      if (failDetach) throw new Error("injected detach failure");
    }
  }
};
worker.URL = URL;
worker.CDP_PROTOCOL_VERSION = "1.3";
worker._cwaBaseSendCommand = async (debuggee, command, args) => {
  if (command === "Runtime.enable") return {};
  assert.equal(command, "Runtime.evaluate");
  return {
    result: {
      value: vm.runInContext(args.expression, pages.get(debuggee.tabId))
    }
  };
};

const request = {
  tabIds: [101, 102],
  sourceLanguage: "en",
  targetLanguage: "es",
  consent: "EXPLICIT_TWO_TAB_OBSERVE_ONLY"
};

async function run() {
  const expression = worker._cwaCaptureV0SemanticPageExpression("en", "es");
  assert.equal(expression.includes("textContent"), false);
  assert.equal(expression.includes(".value"), false);
  assert.equal(expression.includes("innerText"), false);
  assert.equal(expression.includes("outerHTML"), false);
  assert.equal(expression.includes("getAttribute('aria-label')"), false);

  const ok = await worker._cwaCaptureV0SemanticTwoTabs(request);
  assert.equal(ok.observations.length, 2);
  for (const observation of ok.observations) {
    assert.equal(observation.routeVerified, true);
    assert.equal(observation.source_input.candidateCount, 1);
    assert.equal(observation.translated_result.candidateCount, 1);
    assert.equal(observation.resultFamilyStages.rawFamily, 1);
    assert.equal(observation.resultFamilyStages.visibleFamily, 1);
    assert.equal(observation.resultFamilyStages.visibleLeaves, 1);
    assert.equal(observation.source_input.uniqueDescriptor.kind, "textarea");
    assert.equal(observation.source_input.uniqueDescriptor.region, "left");
    assert.equal(observation.translated_result.uniqueDescriptor.region, "right");
  }
  assert.equal(attachCount, 2);
  assert.equal(detachCount, 2);
  assert.equal(ok.semanticFinalityProven, false);
  assert.equal(ok.replayExecutable, false);
  assert.equal(ok.newWriteAuthority, false);
  assert.equal(JSON.stringify(ok).includes("secret input"), false);
  assert.equal(JSON.stringify(ok).includes("private translation"), false);

  b.fields.push(new FakeElement("TEXTAREA", 200, "other private content"));
  const ambiguous = await worker._cwaCaptureV0SemanticTwoTabs(request);
  assert.equal(ambiguous.observations[1].source_input.candidateCount, 2);
  assert.equal(ambiguous.observations[1].source_input.uniqueDescriptor, null);
  b.fields.pop();

  b.outputs[0].left = 400;
  const drifted = await worker._cwaCaptureV0SemanticTwoTabs(request);
  assert.equal(drifted.observations[1].translated_result.uniqueDescriptor.region, "center");
  b.outputs[0].left = 800;

  b.outputs.length = 0;
  const missing = await worker._cwaCaptureV0SemanticTwoTabs(request);
  assert.equal(missing.observations[1].translated_result.candidateCount, 0);
  assert.equal(missing.observations[1].resultFamilyStages.rawFamily, 0);
  assert.equal(missing.observations[1].resultFamilyStages.visibleFamily, 0);
  assert.equal(missing.observations[1].resultFamilyStages.visibleLeaves, 0);
  b.outputs.push(new FakeElement("SPAN", 800, "secret"));

  b.outputs[0].hidden = true;
  const hidden = await worker._cwaCaptureV0SemanticTwoTabs(request);
  assert.equal(hidden.observations[1].translated_result.candidateCount, 0);
  assert.equal(hidden.observations[1].resultFamilyStages.rawFamily, 1);
  assert.equal(hidden.observations[1].resultFamilyStages.visibleFamily, 0);
  assert.equal(hidden.observations[1].resultFamilyStages.visibleLeaves, 0);
  b.outputs[0].hidden = false;

  await assert.rejects(
    () => worker._cwaCaptureV0SemanticTwoTabs({
      ...request, tabIds: [101, 101]
    }),
    /CAPTURE_C1_INVALID_REQUEST/
  );
  assert.equal(attachCount, 10);
  assert.equal(detachCount, 10);

  failDetach = true;
  await assert.rejects(
    () => worker._cwaCaptureV0SemanticTwoTabs(request),
    /CAPTURE_C1_CLEANUP_UNPROVEN/
  );
  assert.equal(detachCount, 11);
  // Regression: the outer Google Translate handler must route C1 rather
  // than falling through to the base handler without a response.
  worker.BRIDGE_PROTOCOL_VERSION = "synthetic";
  worker.importScripts = (script) => {
    assert.ok([
      "service_worker_capability_capture_v0.js",
      "service_worker_capability_capture_c2.js"
    ].includes(script));
  };
  const translatePath = path.join(
    __dirname, "..", "src", "chatgpt_web_adapter",
    "browser_native_extension", "service_worker_google_translate_capability.js"
  );
  vm.runInContext(fs.readFileSync(translatePath, "utf8"), worker);
  const routed = [];
  worker._cwaOnNativeMessageWithCaptureV0 = async (message) => {
    routed.push(message.type);
  };
  const mustNotFallThrough = () => {
    throw new Error("CAPTURE_C1_OUTER_ROUTER_FELL_THROUGH");
  };
  for (const type of [
    "research_capture_translate_demo_v0",
    "research_capture_translate_semantic_v0"
  ]) {
    await worker._cwaOnNativeMessageWithGoogleTranslate(
      { protocol: "synthetic", type, request_id: "routing-test" },
      {},
      mustNotFallThrough
    );
  }
  assert.deepEqual(routed, [
    "research_capture_translate_demo_v0",
    "research_capture_translate_semantic_v0"
  ]);
  let fallback = 0;
  await worker._cwaOnNativeMessageWithGoogleTranslate(
    { protocol: "synthetic", type: "unrelated_operation", request_id: "other" },
    {},
    async () => { fallback++; }
  );
  assert.equal(fallback, 1);
  process.stdout.write("CAPTURE_C1_TWO_DOCUMENT_FIXTURE_OK\n");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
