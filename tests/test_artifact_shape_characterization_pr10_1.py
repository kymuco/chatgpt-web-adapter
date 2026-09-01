from __future__ import annotations

from pathlib import Path

import chatgpt_web_adapter

from chatgpt_web_adapter.product_artifact_observation_pr10_1 import (
    PRODUCT_ARTIFACT_SHAPE_OBSERVED,
    ProductArtifactObservationCollector,
)


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = Path(chatgpt_web_adapter.__file__).parent / "browser_native_extension"
SHAPE_OVERLAY = EXTENSION_ROOT / "service_worker_generated_artifact_shape_pr10_1.js"
OBSERVABILITY = EXTENSION_ROOT / "service_worker_observability.js"
SHAPE_GATE = ROOT / "tools" / "pr10_1_artifact_shape_live_gate.py"


def test_artifact_shape_diagnostic_is_known_but_not_public_observation():
    collector = ProductArtifactObservationCollector()

    value = collector.consume(
        {
            "type": PRODUCT_ARTIFACT_SHAPE_OBSERVED,
            "observation_id": "pr10.1:artifact-shape:1",
            "operation": "probe_filename_anchor",
            "source_content_type": "anchor:exact_filename;path:data.message.metadata.file.name;keys:id,name",
        }
    )

    assert value is None
    assert collector.observations == ()
    assert collector.dropped_event_count == 0


def test_artifact_shape_overlay_is_fixed_probe_anchored_and_bounded():
    source = SHAPE_OVERLAY.read_text(encoding="utf-8")

    assert 'PR101_ARTIFACT_SHAPE_PROBE_FILENAME = "cwa_pr10_1_probe.txt"' in source
    assert 'return "exact_filename"' in source
    assert 'return "filename_suffix"' in source
    assert "PR101_ARTIFACT_SHAPE_MAX_DEPTH = 10" in source
    assert "PR101_ARTIFACT_SHAPE_MAX_NODES = 2048" in source
    assert "PR101_ARTIFACT_SHAPE_MAX_FINDINGS = 16" in source
    assert "_pr101ShapePrivateOrPromptObject" in source
    assert 'value?.content_type === "thoughts"' in source
    assert 'value?.author?.role === "user"' in source


def test_artifact_shape_overlay_exports_summary_not_raw_payload_or_locator_values():
    source = SHAPE_OVERLAY.read_text(encoding="utf-8")
    emit_start = source.index("_pr812Emit(context, {")
    emit_end = source.index("});", emit_start)
    emitted = source[emit_start:emit_end]

    assert "type: PR101_ARTIFACT_SHAPE_EVENT" in emitted
    assert 'operation: "probe_filename_anchor"' in emitted
    assert "source_content_type: summary" in emitted
    for forbidden in ("payload:", "block:", "data:", "url:", "href:", "download_url:", "text:"):
        assert forbidden not in emitted

    assert "rawPayloadExported: false" in source
    assert "artifactLocatorExported: false" in source
    assert "writePerformed: false" in source


def test_artifact_shape_overlay_loads_after_identity_observer_and_before_patch_protocol():
    source = OBSERVABILITY.read_text(encoding="utf-8")
    artifact = 'importScripts("service_worker_generated_artifact_pr10_1.js");'
    shape = 'importScripts("service_worker_generated_artifact_shape_pr10_1.js");'
    patch = 'importScripts("service_worker_normalized_activity_patch_protocol_pr8_12.js");'

    assert source.index(artifact) < source.index(shape) < source.index(patch)


def test_artifact_shape_live_gate_has_zero_write_preflight_and_no_download_path():
    source = SHAPE_GATE.read_text(encoding="utf-8")

    assert "characterizeGeneratedArtifactShapeSupport" in source
    assert '"product_write_budget": 0 if preflight_only else 1' in source
    assert '"download_attempted": False' in source
    assert '"local_write_attempted": False' in source
    assert source.count("run_gate(") == 1
    assert "--acknowledge-live-write" in source
    assert "--preflight-only" in source

    for forbidden in (
        "urlopen(",
        "requests.get(",
        "httpx.get(",
        "chrome.downloads",
        "write_bytes(",
        "write_text(",
        "open(destination",
    ):
        assert forbidden not in source
