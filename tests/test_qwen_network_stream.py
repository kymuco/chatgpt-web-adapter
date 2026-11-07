import shutil
import subprocess
from pathlib import Path

import pytest


def test_sse_handles_byte_boundaries_unicode_and_answer_finality():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    source = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker_qwen_stream.js"
    )
    script = r"""
const vm = require('node:vm'), fs = require('node:fs'), assert = require('node:assert/strict');
const ctx = vm.createContext({TextDecoder, atob, URL});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const chunks = [];
ctx.callback = text => chunks.push(text);
const parser = vm.runInContext('_cwaQwenSseParser(callback)', ctx);
const frame = delta => 'data: ' + JSON.stringify({choices:[{delta}]}) + '\r\n\r\n';
const data = Buffer.from(': comment\r\n\r\n' + frame({phase:'thinking_summary',content:'hidden'}) + frame({phase:'answer',content:'Привет 🌍\n'}) + frame({phase:'answer',content:'world'}) + frame({phase:'answer',status:'finished'}));
for (const byte of data) parser.push(Buffer.from([byte]).toString('base64'));
assert.deepEqual(chunks, ['Привет 🌍\n', 'world']);
assert.equal(parser.finished, true);
parser.push(Buffer.from(frame({phase:'answer',content:'late'})).toString('base64'));
assert.equal(chunks.length, 2);

// Verify buffered bytes are delivered before events arriving during enable.
let listener, resolveEnable;
const events = [];
ctx.chrome = {debugger:{onEvent:{addListener(fn){listener=fn},removeListener(fn){assert.equal(fn,listener);listener=null}}}};
ctx.BRIDGE_PROTOCOL_VERSION = 1;
ctx.postNative = event => events.push(event);
ctx._cwaBaseSendCommand = async (_, method) => method === 'Network.enable' ? {} : await new Promise(resolve => {resolveEnable=resolve});
(async () => {
 const observer = await vm.runInContext('_cwaQwenObserveStream({tabId:1},{request_id:"turn",text:"hello"})',ctx);
 const emit=(method,params)=>listener({tabId:1},method,params);
 emit('Network.requestWillBeSent',{requestId:'r',request:{url:'https://chat.qwen.ai/api/v2/chat/completions',method:'POST',postData:JSON.stringify({messages:[{role:'user',content:'hello'}]})}});
 emit('Network.responseReceived',{requestId:'r',response:{status:200,mimeType:'text/event-stream'}});
 emit('Network.dataReceived',{requestId:'r',data:Buffer.from(frame({phase:'answer',content:'B'})+frame({phase:'answer',status:'finished'})).toString('base64')});
 resolveEnable({bufferedData:Buffer.from(frame({phase:'answer',content:'A'})).toString('base64')});
 assert.equal(await observer.verify(), 'AB');
 assert.deepEqual(events.map(e=>e.event.text),['A','B']);
 observer.close(); assert.equal(listener,null);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", script, str(source)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_read_history_uses_one_get_in_existing_tab_without_writes():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    source = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker_qwen_provider.js"
    )
    script = r"""
const vm = require('node:vm'), fs = require('node:fs'), assert = require('node:assert/strict');
const id = '00000000-0000-4000-8000-000000000001', route = 'https://chat.qwen.ai/c/' + id;
const payload = {data:{chat:{history:{messages:{'a':{role:'assistant',content_list:[]}}}}}};
let tabPresent = true, fetchCount = 0, detached = 0, attached = 0;
const ctx = vm.createContext({
  URL, TextEncoder, CDP_PROTOCOL_VERSION:'1.3', registerProductProviderTurnHandler(){},
  fetch:async (url, options) => {
    assert.equal(url,'https://chat.qwen.ai/api/v2/chats/' + id + '/');
    assert.equal(options.method,'GET'); assert.equal(options.credentials,'include');
    fetchCount++; return {ok:true,json:async()=>payload};
  },
  chrome:{
    storage:{local:{get:async()=>({})}},
    tabs:{
      query:async()=>tabPresent?[{id:17,url:route,status:'complete'}]:[],
      get:async()=>({id:17,url:route,status:'complete'}),
      create:async()=>{throw Error('unexpected tab creation')},
      update:async()=>{throw Error('unexpected tab activation')}
    },
    debugger:{attach:async()=>{attached++},detach:async()=>{detached++}}
  }
});
ctx._cwaBaseSendCommand = async (_target, method, options) => method === 'Runtime.evaluate'
  ? {result:{value:await vm.runInContext(options.expression,ctx)}} : {};
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
ctx.request = {type:'turn',operation:'read_history',conversationId:route};
(async()=>{
  const result = await vm.runInContext('_cwaQwenReadHistory(request)',ctx);
  assert.equal(result.payload,payload);
  assert.equal(result.canonicalCompletionProven,false);
  assert.equal(fetchCount,1); assert.equal(attached,1); assert.equal(detached,1);
  tabPresent=false;
  await assert.rejects(vm.runInContext('_cwaQwenReadHistory(request)',ctx),/TAB_NOT_OPEN/);
  assert.equal(fetchCount,1); assert.equal(attached,1);
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", script, str(source)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
