from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA14 = EXT / "service_worker_rich_input_schema14_repair_pr9_2.js"
GATE14 = PKG / "product_rich_input_live_gate_schema14_pr9_2.py"


def test_schema_14_overlay_is_loaded_after_schema_13():
    text = LOADER.read_text(encoding="utf-8")
    schema13 = 'importScripts("service_worker_rich_input_schema13_repair_pr9_2.js");'
    schema14 = 'importScripts("service_worker_rich_input_schema14_repair_pr9_2.js");'
    assert schema13 in text
    assert schema14 in text
    assert text.index(schema13) < text.index(schema14)


def test_schema_14_rejects_rich_input_model_profile_before_prior_chain():
    text = SCHEMA14.read_text(encoding="utf-8")
    assert "const PR92_SCHEMA14_REPAIR_SCHEMA = 14;" in text
    assert "_pr92Schema14HasAttachmentPaths(message)" in text
    assert "_pr92Schema14HasModelProfileRequirement(message)" in text
    error = 'throw new Error("PR9_2_RICH_INPUT_MODEL_PROFILE_COMBINATION_UNAVAILABLE");'
    prior = "const result = await _pr92Schema14PriorExecuteNativeTurn(message);"
    assert error in text
    assert prior in text
    assert text.index(error) < text.index(prior)


def test_schema_14_guard_is_specific_to_new_composition():
    text = SCHEMA14.read_text(encoding="utf-8")
    assert "Array.isArray(message?.attachmentPaths) && message.attachmentPaths.length > 0" in text
    assert 'typeof message?.requiredModelMode === "string"' in text
    assert "message?.characterizeRichInputSupport !== true" in text
    assert "Text-only model-profile turns and ordinary rich-input turns are unchanged." in text


def test_schema_14_support_contract_is_fail_closed_not_silent_fallback():
    text = SCHEMA14.read_text(encoding="utf-8")
    required = [
        "richInputModelProfileCombinationSupported: false",
        "richInputModelProfileCombinationFailsBeforeStaging: true",
        "richInputModelProfileCombinationFailsBeforeWrite: true",
        "pr810RawPrewriteSelectorExcludedFromRichInput: true",
    ]
    for field in required:
        assert field in text


def test_schema_14_gate_requires_composition_boundary_and_preserves_schema_13():
    text = GATE14.read_text(encoding="utf-8")
    assert "SCHEMA = 14" in text
    assert "class ProductRichInputSchema14LiveProvider" in text
    assert "legacy[\"schema\"] = _v13.SCHEMA" in text
    assert "_v13._validate_support(legacy)" in text
    assert 'support.get("rich_input_model_profile_combination_supported") is not False' in text
    required = [
        "rich_input_model_profile_combination_fails_before_staging",
        "rich_input_model_profile_combination_fails_before_write",
        "pr810_raw_prewrite_selector_excluded_from_rich_input",
    ]
    for key in required:
        assert key in text
    assert "PRODUCT_WRITE_BUDGET = _v13.PRODUCT_WRITE_BUDGET" in text
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text


def test_schema_14_support_probe_is_eighth_no_write_characterization_rpc():
    text = GATE14.read_text(encoding="utf-8")
    assert "This eighth characterization-only RPC carries neither text nor paths." in text
    marker = '"characterizeRichInputSupport": True'
    assert marker in text
    request_block = text[text.index("request_id = str(uuid.uuid4())"):text.index("if response.get", text.index("request_id = str(uuid.uuid4())"))]
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
