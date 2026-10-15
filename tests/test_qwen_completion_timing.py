import shutil
import subprocess
from pathlib import Path

import pytest


def test_completion_wait_tracks_stop_transition_and_text_changes():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    worker = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker_qwen_provider.js"
    )
    script = r"""
const vm = require('node:vm');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[1], 'utf8');
async function run(states) {
  let now = 0, index = 0;
  const ctx = vm.createContext({
    performance: {now: () => now},
    registerProductProviderTurnHandler() {},
    sleep: async ms => {now += ms;},
    _cwaBaseSendCommand: async () => ({result: {value: states[Math.min(index++, states.length - 1)]}})
  });
  vm.runInContext(source, ctx);
  let clicked = 0;
  ctx.document = {querySelector: () => ({
    getBoundingClientRect: () => ({height: 100}),
    querySelector: () => ({textContent: '2000'}),
    querySelectorAll: () => [{textContent: 'Continue', disabled: false, click: () => clicked++}]
  })};
  const age = (allow, submitted) => vm.runInContext(vm.runInContext(`_cwaQwenAgeExpression(2000, ${allow}, ${submitted})`, ctx), ctx);
  assert.equal(age(false, false), 'required');
  assert.equal(clicked, 0);
  assert.equal(age(true, false), 'submitted');
  assert.equal(clicked, 1);
  assert.equal(age(true, true), 'waiting');
  assert.equal(clicked, 1);

  const result = await vm.runInContext('_cwaQwenWaitForFinalText({}, "prompt", new Set(), 20000)', ctx);
  assert.equal(vm.runInContext('_cwaQwenLatestNewText({texts:["same", "same"],answerCount:2}, {answerCount:1})', ctx), 'same');
  assert.equal(vm.runInContext('_cwaQwenLatestNewText({texts:["old"],answerCount:1}, {answerCount:1})', ctx), null);
  return {result, now};
}
const state = (generating, text) => ({generating, texts: text ? [text] : [], url: 'https://chat.qwen.ai/c/test'});
(async () => {
  let r = await run([state(true, 'A'), state(false, 'A')]);
  assert.equal(r.now, 750);
  r = await run([state(false, 'A')]);
  assert.equal(r.now, 9000); // Missing the generation transition keeps the fallback.
  r = await run([state(true, 'A'), state(false, 'A'), state(true, 'AB'), state(false, 'AB'), state(false, 'ABC')]);
  assert.equal(r.now, 1500); // Resumed generation and late rendering both reset settling.
  assert.equal(r.result.text, 'ABC');
  const busy = Array.from({length: 40}, () => state(true, 'A'));
  r = await run([...busy, state(false, 'A')]);
  assert.equal(r.now, 10500); // Never return merely because text is stable during generation.
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    result = subprocess.run(
        [node, "-e", script, str(worker)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
