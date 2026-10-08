// Synthetic page-level contract test; never connects to a browser or network.
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const jsPath = path.join(
  __dirname, "..", "src", "chatgpt_web_adapter",
  "browser_native_extension", "service_worker_capability_capture_v0.js"
);
const worker = vm.createContext({});
vm.runInContext(fs.readFileSync(jsPath, "utf8"), worker);

class Element {
  getBoundingClientRect() { return { width: 100, height: 30, left: 0 }; }
  contains(other) { return this === other; }
}
class HTMLTextAreaElement extends Element {
  constructor() { super(); this.value = ""; }
}
const source = new HTMLTextAreaElement();
const output = new Element();
output.textContent = "";
const listeners = new Map();
const document = {
  querySelectorAll(selector) {
    if (selector.startsWith("textarea")) return [source];
    if (selector.startsWith("[jsname")) return [output];
    throw new Error("Unexpected selector");
  },
  addEventListener(type, listener) {
    if (type !== "input") throw new Error("Unexpected listener");
    listeners.set(type, listener);
  },
  removeEventListener(type, listener) {
    if (listeners.get(type) === listener) listeners.delete(type);
  }
};
const page = vm.createContext({
  window: {},
  document,
  Element,
  HTMLTextAreaElement,
  getComputedStyle: () => ({ display: "block", visibility: "visible" }),
  location: { href: "https://translate.google.com/?sl=en&tl=es&op=translate" },
  URL
});

function evaluate(mode) {
  const expression = worker._cwaCaptureV0PageExpression(mode);
  return vm.runInContext(expression, page);
}

const installed = evaluate("install");
assert.equal(installed.ready, true);
assert.equal(listeners.has("input"), true);

let observation = evaluate("observe");
assert.equal(observation.inputEvents, 0);
assert.equal(observation.candidateCount, 0);

// The user's demonstration is simulated by one page-owned input event.
// The observer does not send this input and must never export its contents.
source.value = "super private demonstration input";
listeners.get("input")({ target: source });
output.textContent = "private translated output";
observation = evaluate("observe");
assert.equal(observation.inputEvents, 1);
assert.equal(observation.candidateCount, 1);
assert.equal(observation.candidateIdentityResolved, true);
assert.equal(observation.sourceRoute, "en");
assert.equal(observation.targetRoute, "es");
const serialized = JSON.stringify(observation);
assert.equal(serialized.includes("super private"), false);
assert.equal(serialized.includes("private translated"), false);

const removed = evaluate("remove");
assert.equal(removed.removed, true);
assert.equal(listeners.has("input"), false);
assert.equal(evaluate("observe").ready, false);
process.stdout.write("CAPTURE_V0_DOM_FIXTURE_OK\n");
