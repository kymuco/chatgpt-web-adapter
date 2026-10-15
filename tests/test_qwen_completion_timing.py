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
    getComputedStyle: () => ({display:'block'}),
    sleep: async ms => {now += ms;},
    _cwaBaseSendCommand: async (_, command, args) => ({result: {value:
      args?.expression?.includes('age-confirmation-modal') ? 'absent' :
      states[Math.min(index++, states.length - 1)]
    }})
  });
  vm.runInContext(source, ctx);
  let clicked = 0;
  ctx.window = {innerWidth: 1600, innerHeight: 900};
  ctx.document = {querySelector: () => ({
    getAttribute: () => null,
    getBoundingClientRect: () => ({left: 10, top: 10, width: 800, height: 300}),
    querySelector: () => ({textContent: '2000'}),
    querySelectorAll: () => [{
      textContent: 'Continue', disabled: false,
      getBoundingClientRect: () => ({left: 40, top: 100, width: 160, height: 40}),
      click: () => clicked++
    }]
  })};
  const age = (allow, submitted) => vm.runInContext(vm.runInContext(`_cwaQwenAgeExpression(2000, ${allow}, ${submitted})`, ctx), ctx);
  assert.equal(age(false, false), 'required');
  assert.equal(age(true, false).action, 'confirm_age');
  assert.equal(age(true, false).x, 120);
  assert.equal(age(true, false).y, 120);
  assert.equal(age(true, true), 'waiting');
  assert.equal(clicked, 0, 'reading age state never invokes synthetic .click()');

  const result = await vm.runInContext('_cwaQwenWaitForFinalText({}, "prompt", new Set(), 20000)', ctx);
  assert.equal(vm.runInContext('_cwaQwenLatestNewText({texts:["same", "same"],answerCount:2}, {answerCount:1})', ctx), 'same');
  assert.equal(vm.runInContext('_cwaQwenLatestNewText({texts:["old"],answerCount:1}, {answerCount:1})', ctx), null);
  return {result, now};
}
const state = (generating, text) => ({generating, texts: text ? [text] : [], url: 'https://chat.qwen.ai/c/test'});
(async () => {
  let r = await run([state(true, 'A'), state(false, 'A')]);
  assert.equal(r.now, 9250); // A transient Stop-button disappearance is not finality.
  r = await run([state(false, 'A')]);
  assert.equal(r.now, 9000); // Same stability threshold even when no Stop transition was seen.
  r = await run([state(true, 'A'), state(false, 'A'), state(true, 'AB'), state(false, 'AB'), state(false, 'ABC')]);
  assert.equal(r.now, 10000); // Resumed generation and late rendering reset the quiet window.
  assert.equal(r.result.text, 'ABC');
  r = await run([
    state(true, 'По состоянию на сезон 2026 года'),
    ...Array.from({length: 12}, () => state(false, 'По состоянию на сезон 2026 года')),
    state(true, 'По состоянию на сезон 2026 года лидером'),
    state(false, 'По состоянию на сезон 2026 года лидером'),
    state(false, 'По состоянию на сезон 2026 года лидером является пилот'),
  ]);
  assert.equal(r.result.text, 'По состоянию на сезон 2026 года лидером является пилот');
  assert.ok(r.now >= 12000, 'the first 3-second pause must not finalize the partial answer');
  const busy = Array.from({length: 40}, () => state(true, 'A'));
  r = await run([...busy, state(false, 'A')]);
  assert.equal(r.now, 19000); // Never return while generating even if the text is stable.
  await assert.rejects(
    () => run(Array.from({length: 90}, () => state(true, 'A'))),
    /PAGE_FINALITY_TIMEOUT/
  );
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    result = subprocess.run(
        [node, "-e", script, str(worker)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_age_gate_after_send_is_handled_once_or_fails_explicitly():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    worker = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker_qwen_provider.js"
    )
    script = r"""
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
let now=0, ageCalls=0, clicks=0, evalCalls=0;
const ctx=vm.createContext({
  performance:{now:()=>now},
  registerProductProviderTurnHandler(){},
  sleep:async ms=>{now+=ms},
  _cwaBaseSendCommand:async (_,method,args)=>{
    if (method!=='Runtime.evaluate') throw Error('unexpected CDP call');
    evalCalls++;
    if (args.expression.includes('age-confirmation-modal')) {
      ageCalls++;
      const stage=ageCalls===1?'submitted':ageCalls===2?'waiting':'absent';
      if (stage==='submitted') clicks++;
      return {result:{value:stage}};
    }
    return {result:{value:{generating:false,texts:['Full answer'],answerCount:1,url:'https://chat.qwen.ai/c/id'}}};
  }
});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
(async()=>{
 const out=await vm.runInContext('_cwaQwenWaitForFinalText({}, "question", {answerCount:0}, 30000, null, {autoConfirmAge:true,birthYear:2000},{})',ctx);
 assert.equal(out.text,'Full answer');
 assert.equal(clicks,1,'age clicked once after write');
 assert.ok(now>=9000);
 // Background dialog is stuck after the click. Fail quickly rather than hang until the turn timeout.
 now=0; ageCalls=0; clicks=0;
 ctx._cwaQwenEvaluate=async ()=>{ageCalls++; if(ageCalls===1){clicks++;return 'submitted'}return 'waiting'};
 await assert.rejects(
  ()=>vm.runInContext('_cwaQwenWaitForComposer({}, 30000, {autoConfirmAge:true,birthYear:2000}, {})',ctx),
  /QWEN_AGE_CONFIRMATION_STALLED/
 );
 assert.equal(clicks,1,'never repeat the age confirmation click');
 assert.ok(now>=12000&&now<14000);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", script, str(worker)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_age_confirmation_uses_trusted_cdp_mouse_and_never_repeats_continue():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    worker = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker_qwen_provider.js"
    )
    script = r"""
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
let now=0, agePolls=0;
const mouse=[];
const ctx=vm.createContext({
 performance:{now:()=>now},
 registerProductProviderTurnHandler(){},
 _cwaBaseSendCommand:async (_d,method,args)=>{
  if(method==='Input.dispatchMouseEvent'){mouse.push({...args});return {};}
  throw Error('Unexpected '+method);
 }
});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
ctx._cwaQwenEvaluate=async()=>{
 agePolls++;
 return agePolls===1 ? {action:'confirm_age',x:120,y:240}
      : agePolls===2 ? 'waiting' : 'absent';
};
(async()=>{
 const s={};
 assert.equal(await vm.runInContext('_cwaQwenHandleAgeGate({}, {autoConfirmAge:true,birthYear:2000}, globalState)',Object.assign(ctx,{globalState:s})),true);
 assert.equal(s.submitted,true);
 assert.deepEqual(mouse.map(m=>m.type), ['mouseMoved','mousePressed','mouseReleased']);
 assert.ok(mouse.every(m=>m.x===120&&m.y===240));
 assert.equal(await vm.runInContext('_cwaQwenHandleAgeGate({}, {autoConfirmAge:true,birthYear:2000}, globalState)',ctx),true);
 assert.equal(mouse.length,3,'must not re-click Continue on still visible dialog');
 assert.equal(await vm.runInContext('_cwaQwenHandleAgeGate({}, {autoConfirmAge:true,birthYear:2000}, globalState)',ctx),false);
 assert.equal(s.submitted,false);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", script, str(worker)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
