from __future__ import annotations

from pathlib import Path

import chatgpt_web_adapter


EXTENSION_ROOT = Path(chatgpt_web_adapter.__file__).parent / "browser_native_extension"
ARTIFACT_OVERLAY = EXTENSION_ROOT / "service_worker_generated_artifact_pr10_1.js"
OBSERVABILITY = EXTENSION_ROOT / "service_worker_observability.js"


def _source() -> str:
    return ARTIFACT_OVERLAY.read_text(encoding="utf-8")


def test_generated_artifact_overlay_requires_explicit_product_owned_identity():
    source = _source()

    for key in ("artifact_id", "file_id", "asset_id", "generated_file_id"):
        assert key in source
    assert "if (!artifactId) continue" in source
    assert "synthetic" not in source.lower()
    assert "message order" in source


def test_generated_artifact_overlay_never_exports_locator_values():
    source = _source()
    emitted_block = source[source.index("_pr812Emit(context, {") : source.index("});", source.index("_pr812Emit(context, {"))]

    for key in ("download_url", "download_uri", "signed_url", "url:", "href:"):
        assert key not in emitted_block
    assert "download_available: artifact.downloadAvailable" in emitted_block
    assert "artifact_id: artifact.artifactId" in emitted_block


def test_generated_artifact_overlay_ignores_string_content_parts():
    source = _source()

    assert 'if (typeof part === "string") continue;' in source
    assert "_pr101CandidateFromObject(part" in source
    assert "_pr812RawTextForClassification" not in source
    assert ".textContent" not in source
    assert ".innerText" not in source


def test_generated_artifact_overlay_sanitizes_filename_and_identity():
    source = _source()

    assert "/^[A-Za-z0-9_.:-]+$/" in source
    assert "text.length > 192" in source
    assert "text.length > 255" in source
    assert "[\\\\/\\u0000-\\u001f]" in source
    for marker in ("token", "secret", "credential", "authorization", "cookie"):
        assert marker in source


def test_generated_artifact_overlay_loads_after_pr10_router_and_before_patch_protocol():
    source = OBSERVABILITY.read_text(encoding="utf-8")
    router = 'importScripts("service_worker_connector_router_characterization_pr10_0.js");'
    artifact = 'importScripts("service_worker_generated_artifact_pr10_1.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'

    assert source.index(router) < source.index(artifact) < source.index(patch)
