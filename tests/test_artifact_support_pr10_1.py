from __future__ import annotations

from pathlib import Path

import chatgpt_web_adapter


EXT = Path(chatgpt_web_adapter.__file__).parent / "browser_native_extension"
SUPPORT = EXT / "service_worker_connector_support_pr10_0.js"


def test_artifact_support_extends_existing_outermost_no_write_contract():
    source = SUPPORT.read_text(encoding="utf-8")

    for contract in (
        "generatedArtifactObservationSupported: true",
        "generatedArtifactObservationSchemaVersion: 1",
        "explicitArtifactIdentityRequired: true",
        "artifactLocatorExported: false",
        "artifactObservationGrantsDownloadAuthority: false",
        "artifactObservationGrantsOverwriteAuthority: false",
        "writePerformed: false",
    ):
        assert contract in source

    assert "message?.characterizeConnectorObservationSupport === true" in source
    assert "message?.text != null" in source
    assert "message?.attachmentPaths != null" in source


def test_artifact_support_proof_does_not_add_download_or_filesystem_primitives():
    source = SUPPORT.read_text(encoding="utf-8")

    for forbidden in (
        "chrome.downloads",
        "Browser.setDownloadBehavior",
        "Page.setDownloadBehavior",
        "Input.dispatchMouseEvent",
        "Input.dispatchKeyEvent",
        ".click()",
        "writeFile",
        "write_bytes",
    ):
        assert forbidden not in source
