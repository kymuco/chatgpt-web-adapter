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
 await observer.verify();
 assert.deepEqual(events.map(e=>e.event.text),['A','B']);
 observer.close(); assert.equal(listener,null);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", script, str(source)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
