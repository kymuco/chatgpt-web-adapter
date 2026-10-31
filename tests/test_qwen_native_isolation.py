"""Offline proof of the independent Qwen native-bridge boundary.

These tests do not start Chrome, send prompts, register native hosts, or touch
the user's actual production CWA deployment.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter import browser_native_protocol, qwen_native
from chatgpt_web_adapter.qwen_web import QwenBrowserTurnProvider

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src/chatgpt_web_adapter/browser_native_extension"


def test_qwen_native_descriptor_and_host_are_independent(monkeypatch, tmp_path):
    production_root = tmp_path / "browser-native"
    monkeypatch.setattr(
        qwen_native,
        "default_browser_native_state_dir",
        lambda: production_root,
    )
    expected = tmp_path / "qwen-native"
    assert qwen_native.state_dir() == expected
    assert qwen_native.HOST_NAME != browser_native_protocol.HOST_NAME
    monkeypatch.setattr(qwen_native, "state_dir", lambda: expected)
    assert QwenBrowserTurnProvider().descriptor_path == expected / "bridge.json"
    assert QwenBrowserTurnProvider().descriptor_path != (
        production_root / "bridge.json"
    )


def test_windows_qwen_native_registration_uses_single_registry_separators(
    monkeypatch, tmp_path: Path
):
    """Simulate the Windows registry call without writing to a real registry."""
    root = tmp_path / "qwen-native"
    executable_dir = tmp_path / "Scripts"
    executable_dir.mkdir()
    (executable_dir / "qwen-web-adapter-native-host.exe").write_text(
        "placeholder", encoding="utf-8"
    )
    monkeypatch.setattr(qwen_native, "state_dir", lambda: root)
    monkeypatch.setattr(qwen_native, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        qwen_native.sys, "executable", str(executable_dir / "python.exe")
    )
    monkeypatch.setattr(
        qwen_native.sys,
        "argv",
        ["qwen-native", "--extension-id", "abcdefghijklmnopabcdefghijklmnop"],
    )
    calls = []

    class RegistryKey:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def create_key(root_key, path):
        calls.append((root_key, path))
        return RegistryKey()

    def set_value(_key, name, _reserved, _type, value):
        calls.append((name, value))

    monkeypatch.setitem(
        sys.modules,
        "winreg",
        SimpleNamespace(
            HKEY_CURRENT_USER=1,
            REG_SZ=1,
            CreateKey=create_key,
            SetValueEx=set_value,
        ),
    )

    qwen_native.main()

    assert calls[0] == (
        1,
        rf"Software\Google\Chrome\NativeMessagingHosts\{qwen_native.HOST_NAME}",
    )
    assert calls[1] == (None, str(root / "native-host.json"))


def test_qwen_worker_is_not_loaded_by_shared_cwa():
    runtime = (EXT / "service_worker_runtime.js").read_text(encoding="utf-8")
    manifest = (EXT / "manifest.json").read_text(encoding="utf-8")
    qwen_worker = (ROOT / "src/chatgpt_web_adapter/qwen_native_worker.js").read_text(
        encoding="utf-8"
    )
    assert "service_worker_qwen_provider.js" not in runtime
    assert "service_worker_qwen_stream.js" not in runtime
    assert "https://chat.qwen.ai/*" not in manifest
    assert 'connectNative("com.kymuco.qwen_web_adapter")' in qwen_worker
    assert 'importScripts("service_worker_qwen_stream.js", ' in qwen_worker
    assert '"service_worker_qwen_provider.js");' in qwen_worker
    assert "com.kymuco.chatgpt_web_adapter" not in qwen_worker


def test_qwen_worker_delivers_single_turn_and_enables_input_focus():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not available")

    worker = ROOT / "src/chatgpt_web_adapter/qwen_native_worker.js"
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
let receive;
const sent = [], cdp = [], imports = [];
const port = {
  postMessage(value){sent.push(value)},
  onMessage:{addListener(fn){receive=fn}},
  onDisconnect:{addListener(){}}
};
const chrome = {
  runtime:{
    id:'experimental-qwen-id',
    connectNative(name){
      assert.equal(name,'com.kymuco.qwen_web_adapter');
      return port;
    },
    onStartup:{addListener(){}},
    onInstalled:{addListener(){}}
  },
  debugger:{
    async sendCommand(target,method,params){
      cdp.push([method,params]); return {};
    }
  }
};
const ctx = vm.createContext({
  chrome,
  importScripts(...paths){imports.push(...paths)},
  setTimeout,
  Promise
});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
assert.deepEqual(imports, [
  'service_worker_qwen_stream.js',
  'service_worker_qwen_provider.js'
]);
assert.equal(sent[0].type,'hello');
assert.equal(sent[0].extensionId,'experimental-qwen-id');
ctx.registerProductProviderTurnHandler('qwen',async request=>({
  providerId:'qwen',
  responseText:request.text.toUpperCase()
}));
(async()=>{
  await ctx._cwaBaseSendCommand(
    {tabId:1},'Input.insertText',{text:'hi'}
  );
  assert.deepEqual(cdp.map(x=>x[0]),[
    'Emulation.setFocusEmulationEnabled','Input.insertText'
  ]);
  assert.equal(cdp[0][1].enabled,true);
  assert.equal(cdp[1][1].text,'hi');
  await ctx._cwaBaseSendCommand({tabId:1},'Runtime.enable');
  assert.equal(cdp[2][0],'Runtime.enable');
  assert.equal(cdp.length,3);
  await receive({protocol:1,type:'turn',request_id:'one',
    providerId:'qwen',text:'hi'});
  assert.equal(sent.length,2);
  assert.equal(sent[1].type,'turn_result');
  assert.equal(sent[1].request_id,'one');
  assert.equal(sent[1].responseText,'HI');
  await receive({protocol:1,type:'turn',request_id:'two',
    providerId:'chatgpt',text:'must-not-run'});
  assert.equal(sent[2].ok,false);
  assert.match(sent[2].error,/QWEN_PROVIDER_REQUIRED/);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    completed = subprocess.run(
        [node, "-e", script, str(worker)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
