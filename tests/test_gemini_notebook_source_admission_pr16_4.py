from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def test_gemini_notebook_characterization_worker_is_valid_javascript() -> None:
    worker = EXT / "service_worker_gemini_notebook_capability.js"
    subprocess.run(
        ["node", "--check", str(worker)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_gemini_notebook_characterization_is_read_only_and_product_local() -> None:
    worker = (EXT / "service_worker_gemini_notebook_capability.js").read_text(
        encoding="utf-8"
    )

    assert "https://notebook.google" in worker
    assert "https://notebooklm.google.com" in worker
    assert 'message?.type !== "characterize_gemini_notebook"' in worker

    assert "chrome.tabs.query" in worker
    assert "chrome.tabs.create" not in worker
    assert "chrome.tabs.update" not in worker
    assert ".click()" not in worker
    assert "InputEvent" not in worker
    assert "dispatchEvent(" not in worker

    assert "fetch(" not in worker
    assert "XMLHttpRequest" not in worker
    assert "Network.enable" not in worker
    assert "Network.request" not in worker
    assert "batchexecute" not in worker

    assert "Runtime.evaluate" in worker
    assert "readOnly: true" in worker
    assert "GEMINI_NOTEBOOK_CHARACTERIZATION_TAB_MISSING" in worker
    assert "GEMINI_NOTEBOOK_CHARACTERIZATION_TAB_AMBIGUOUS" in worker


def test_gemini_notebook_characterization_is_explicit_extension_layer() -> None:
    manifest = (EXT / "manifest.json").read_text(encoding="utf-8")
    runtime = (EXT / "service_worker_runtime.js").read_text(encoding="utf-8")
    router = (EXT / "service_worker_native_message_router.js").read_text(
        encoding="utf-8"
    )

    assert "https://notebook.google/*" in manifest
    assert "https://notebooklm.google.com/*" in manifest
    assert 'importScripts("service_worker_gemini_notebook_capability.js");' in runtime
    assert runtime.index("service_worker_gemini_provider.js") < runtime.index(
        "service_worker_gemini_notebook_capability.js"
    )
    assert runtime.index(
        "service_worker_gemini_notebook_capability.js"
    ) < runtime.index("service_worker_google_translate_capability.js")
    assert "_cwaOnNativeMessageWithGeminiNotebook(" in router
    assert "_cwaOnNativeMessageWithGoogleTranslate(" in router


def test_gemini_notebook_characterization_uses_shared_authority_lane() -> None:
    host = (ROOT / "src" / "chatgpt_web_adapter" / "browser_native_host.py").read_text(
        encoding="utf-8"
    )

    assert '"characterize_gemini_notebook",' in host
    assert '"characterize_gemini_notebook": 10_000' in host
    assert "_claim_authority_lane(operation, lease_id)" in host


def test_gemini_notebook_characterization_cli_does_not_mutate_product() -> None:
    script = (
        ROOT / "src" / "chatgpt_web_adapter" / "gemini_notebook_web_characterization.py"
    ).read_text(encoding="utf-8")

    assert '"type": "characterize_gemini_notebook"' in script
    assert '"read_only"' in script
    assert "add_url_source" not in script
    assert "translate_text" not in script
    assert "send_text" not in script


def test_gemini_notebook_spike_keeps_shared_architecture_unpromoted() -> None:
    record = (
        ROOT
        / "docs"
        / "engineering"
        / "pr16_4_gemini_notebook_source_admission_spike.md"
    ).read_text(encoding="utf-8")

    assert "existing owned consumer Gemini Notebook" in record
    assert "durable source admission" in record
    assert "Gemini Notebook Enterprise has preview APIs" in record
    assert "generic HostedCapabilityRuntime" in record
    assert "no automatic replay" in record
    assert "PAGE_DOM_DURABLE_SOURCE_ADMISSION" in record
    assert "private batchexecute reproduction" in record
