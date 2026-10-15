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
  assert.equal(r.now, 3750); // A transient Stop-button disappearance is not finality.
  r = await run([state(false, 'A')]);
  assert.equal(r.now, 3500); // Same stability threshold even when no Stop transition was seen.
  r = await run([state(true, 'A'), state(false, 'A'), state(true, 'AB'), state(false, 'AB'), state(false, 'ABC')]);
  assert.equal(r.now, 4500); // Resumed generation and late rendering reset the quiet window.
  assert.equal(r.result.text, 'ABC');
  r = await run([
    state(true, 'По состоянию на сезон 2026 года'),
    ...Array.from({length: 12}, () => state(false, 'По состоянию на сезон 2026 года')),
    state(true, 'По состоянию на сезон 2026 года лидером'),
    state(false, 'По состоянию на сезон 2026 года лидером'),
    state(false, 'По состоянию на сезон 2026 года лидером является пилот'),
  ]);
  assert.equal(r.result.text, 'По состоянию на сезон 2026 года лидером является пилот');
  assert.ok(r.now >= 7000, 'the first 3-second pause must not finalize the partial answer');
  const busy = Array.from({length: 40}, () => state(true, 'A'));
  r = await run([...busy, state(false, 'A')]);
  assert.equal(r.now, 13500); // Never return while generating even if the text is stable.
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
    if (method==='Input.dispatchMouseEvent') {
      if (args.type==='mouseReleased') clicks++;
      return {};
    }
    if (method!=='Runtime.evaluate') throw Error('unexpected CDP call');
    evalCalls++;
    if (args.expression.includes('age-confirmation-modal')) {
      ageCalls++;
      const stage=ageCalls===1?{action:'confirm_age',x:120,y:240}:ageCalls===2?'waiting':'absent';
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
 assert.ok(now>=3500);
 // Background dialog is stuck after the click. Fail quickly rather than hang until the turn timeout.
 now=0; ageCalls=0; clicks=0;
 ctx._cwaQwenEvaluate=async ()=>{ageCalls++; return ageCalls===1?{action:'confirm_age',x:120,y:240}:'waiting'};
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


def test_delayed_age_modal_blocks_send_until_it_disappears_and_composer_stabilizes():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    worker = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker_qwen_provider.js"
    )
    script = r"""
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
let now=0, confirmed=false;
const events=[];
const ctx=vm.createContext({
 performance:{now:()=>now},
 registerProductProviderTurnHandler(){},
 sleep:async ms=>{now+=ms},
 _cwaBaseSendCommand:async (_d,method,args)=>{
  if(method==='Input.dispatchMouseEvent'){
   events.push(args.type);
   if(args.type==='mouseReleased') confirmed=true;
   return {};
  }
  if(method==='Runtime.evaluate'){
   if(args.expression.includes('age-confirmation-modal')){
    if(now>=500&&!confirmed)return {result:{value:{action:'confirm_age',x:120,y:240}}};
    return {result:{value:'absent'}};
   }
   return {result:{value:{found:true}}};
  }
  throw Error('unexpected CDP method '+method);
 }
});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
(async()=>{
 await vm.runInContext('_cwaQwenWaitForComposer({}, 5000, {autoConfirmAge:true,birthYear:2000}, {})',ctx);
 assert.ok(confirmed, 'the late age dialog must be acknowledged');
 assert.deepEqual(events,['mouseMoved','mousePressed','mouseReleased']);
 assert.ok(now>=2000, 'composer must be stable again after the late dialog');
 assert.ok(now<5000);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", script, str(worker)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_qwen_single_send_is_after_composer_ready_and_fails_before_click_on_reset():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    worker = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker_qwen_provider.js"
    )
    script = r"""
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const events=[];
let now=0, reset=false;
const ctx=vm.createContext({
  performance:{now:()=>now},
  registerProductProviderTurnHandler(){},
  sleep:async ms=>{now+=ms},
  _cwaBaseSendCommand:async (_,method,params)=>{
    throw Error('unexpected '+method);
  }
});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
ctx._cwaQwenWaitForComposer=async()=>{events.push('page_ready')};
ctx._cwaQwenHandleAgeGate=async()=>false;
ctx._cwaQwenEvaluate=async(_,expr)=>{
  if(expr.includes('message-input-textarea') && expr.includes('InputEvent')){
    events.push('typed');
    return {written:true};
  }
  if(expr.includes('send_control_not_ready')){
    if(expr.endsWith(',true)')){
      events.push('clicked');
      return {ready:true,submitted:true,mechanism:'dom_click'};
    }
    events.push('checked');
    return reset ? {ready:false,reason:'composer_value_mismatch'} :
      {ready:true};
  }
  throw Error('unexpected expression');
};
(async()=>{
 await vm.runInContext('_cwaQwenSubmitOnce({}, "My question", 6000)',ctx);
 assert.deepEqual(events,['page_ready','typed','checked','clicked']);
 events.length=0;reset=true;now=0;
 await assert.rejects(
  ()=>vm.runInContext('_cwaQwenSubmitOnce({}, "My question", 6000)',ctx),
  /QWEN_PRE_SUBMIT_COMPOSER_VALUE_MISMATCH/
 );
 assert.deepEqual(events,['page_ready','typed','checked'],
   'composer erased after age handling must never wait 150s or click Send');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", script, str(worker)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_qwen_no_postclick_start_fails_within_15s_not_at_bridge_timeout():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    worker = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker_qwen_provider.js"
    )
    script = r"""
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
let now=0;
const ctx=vm.createContext({
  performance:{now:()=>now},
  registerProductProviderTurnHandler(){},
  sleep:async ms=>{now+=ms}
});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
ctx._cwaQwenHandleAgeGate=async()=>false;
ctx._cwaQwenEvaluate=async()=>({
  generating:false,answerCount:0,texts:[],url:'https://chat.qwen.ai/'
});
(async()=>{
 await assert.rejects(
  ()=>vm.runInContext('_cwaQwenWaitForFinalText({}, "prompt", {answerCount:0, initialUrl:"https://chat.qwen.ai/"}, 30000)',ctx),
  /QWEN_POST_SUBMIT_START_UNOBSERVED/
 );
 assert.ok(now>=15000&&now<16000, 'no silent 150-second wait');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", script, str(worker)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_background_tab_send_uses_single_dom_click_and_is_not_sent_by_cdp_mouse():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    worker = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker_qwen_provider.js"
    )
    script = r"""
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
let clicks=0;
class Element {}
const composer=Object.assign(new Element(),{
 value:'привет',isConnected:true,
 getBoundingClientRect(){return {width:100,height:50}}
});
const send=Object.assign(new Element(),{
 disabled:false,isConnected:true,
 getBoundingClientRect(){return {width:30,height:30}},
 getAttribute(){return null},
 click(){clicks++}
});
const ctx=vm.createContext({
  registerProductProviderTurnHandler(){},
  Element,
  getComputedStyle:()=>({display:'block',visibility:'visible'}),
  document:{
    querySelector:()=>null,
    querySelectorAll:(selector)=>{
      if(selector.includes('textarea.message-input-textarea')) return [composer];
      if(selector.includes('button.send-button')) return [send];
      return [];
    }
  }
});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const observe=vm.runInContext(vm.runInContext('_cwaQwenSubmitExpression("привет")',ctx),ctx);
assert.equal(observe.ready,true);
assert.equal(clicks,0,'readiness check never sends');
const submit=vm.runInContext(vm.runInContext('_cwaQwenSubmitExpression("привет",true)',ctx),ctx);
assert.equal(submit.submitted,true);
assert.equal(submit.mechanism,'dom_click');
assert.equal(clicks,1);
composer.value=''; // textarea was reset after a navigation
const lost=vm.runInContext(vm.runInContext('_cwaQwenSubmitExpression("привет",true)',ctx),ctx);
assert.equal(lost.reason,'composer_value_mismatch');
assert.equal(clicks,1,'no send from a cleared composer');
"""
    result = subprocess.run(
        [node, "-e", script, str(worker)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_qwen_no_start_error_contains_bounded_private_data_free_dom_evidence():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    worker = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker_qwen_provider.js"
    )
    script = r"""
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
let now=0;
const ctx=vm.createContext({
 performance:{now:()=>now},
 registerProductProviderTurnHandler(){},
 sleep:async ms=>{now+=ms}
});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
ctx._cwaQwenHandleAgeGate=async()=>false;
ctx._cwaQwenEvaluate=async()=>({
 generating:false,answerCount:0,texts:[],url:'https://chat.qwen.ai/',
 editorState:'prompt_present',sendState:'enabled',pageVisibility:'hidden'
});
(async()=>{
 await assert.rejects(
  ()=>vm.runInContext('_cwaQwenWaitForFinalText({}, "PRIVATE-PROMPT", {answerCount:0,initialUrl:"https://chat.qwen.ai/"}, 30000)',ctx),
  error=>{
   assert.match(error.message,/editor=prompt_present send=enabled visibility=hidden/);
   assert.equal(error.message.includes('PRIVATE-PROMPT'),false);
   return true;
  }
 );
 assert.ok(now>=15000&&now<16000);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", script, str(worker)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_qwen_dual_response_is_not_treated_as_a_single_canonical_answer():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    worker = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker_qwen_provider.js"
    )
    script = r"""
const vm = require('node:vm'), fs = require('node:fs'), assert = require('node:assert/strict');
let now = 0, rendered = 0;
const ctx = vm.createContext({
  performance: {now: () => now},
  registerProductProviderTurnHandler() {},
  sleep: async ms => {now += ms}
});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
ctx._cwaQwenHandleAgeGate = async () => false;
ctx._cwaQwenEvaluate = async (_, expression) => (
  expression.includes("InputEvent")
    ? {found:false, dualPending:true}
    : {
      generating:false, dualPending:true, answerCount:2,
      texts:["Candidate 1", "Candidate 2"], url:"https://chat.qwen.ai/c/dual"
    }
);
(async () => {
  await assert.rejects(
    () => vm.runInContext(
      '_cwaQwenWaitForFinalText({}, "prompt", {answerCount:0,initialUrl:"https://chat.qwen.ai/"}, 20000, () => {throw Error("MUST_NOT_STREAM_DUAL")})',
      ctx
    ),
    /QWEN_DUAL_RESPONSE_SELECTION_REQUIRED/
  );
  assert.equal(now, 0, 'no delayed selection or silent last-node answer');
  await assert.rejects(
    () => vm.runInContext('_cwaQwenWaitForComposer({}, 20000, {}, {})', ctx),
    /QWEN_DUAL_RESPONSE_SELECTION_REQUIRED/
  );

  // Confirm the text shown by Qwen really maps to our detection, without
  // relying solely on a test-supplied 'dualPending' flag.
  ctx.location = {href:"https://chat.qwen.ai/c/dual"};
  ctx.document = {
    body:{innerText:"This feedback will help us evaluate and improve Qwen's performance.\\nWhich response do you prefer? Select one to continue.\\nResponse 1\\nResponse 2"},
    visibilityState:"visible",
    querySelectorAll: () => [],
    querySelector: () => null
  };
  const snap = vm.runInContext(vm.runInContext('_cwaQwenSnapshotExpression("prompt")',ctx),ctx);
  assert.equal(snap.dualPending,true);
  const ready = vm.runInContext(vm.runInContext('_cwaQwenComposerExpression()',ctx),ctx);
  assert.equal(ready.dualPending,true);
})().catch(e => {console.error(e); process.exitCode = 1});
"""
    result = subprocess.run(
        [node, "-e", script, str(worker)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
