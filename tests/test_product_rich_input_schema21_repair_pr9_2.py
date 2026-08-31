from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "chatgpt_web_adapter"
EXT = PKG / "browser_native_extension"
LOADER = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
SCHEMA7 = EXT / "service_worker_rich_input_schema7_core_pr9_2.js"
SCHEMA20 = EXT / "service_worker_rich_input_schema20_repair_pr9_2.js"
SCHEMA21 = EXT / "service_worker_rich_input_schema21_repair_pr9_2.js"
GATE21 = PKG / "product_rich_input_live_gate_schema21_pr9_2.py"


def test_schema_21_overlay_is_loaded_after_schema_20():
    text = LOADER.read_text(encoding="utf-8")
    schema20 = 'importScripts("service_worker_rich_input_schema20_repair_pr9_2.js");'
    schema21 = 'importScripts("service_worker_rich_input_schema21_repair_pr9_2.js");'
    assert schema20 in text
    assert schema21 in text
    assert text.index(schema20) < text.index(schema21)


def test_schema_21_bypasses_schema_20_early_marker_wrapper():
    text = SCHEMA21.read_text(encoding="utf-8")
    start = text.index("_pr92Schema7AtomicAttachmentSubmitExpression = function")
    end = text.index("executeNativeTurn = async function", start)
    block = text[start:end]
    assert "_pr92Schema20PriorAtomicAttachmentSubmitExpression(" in block
    assert "_pr92Schema20PageSideArmProtectedSubmit" not in block
    assert "PR92_SCHEMA21_CLICK_NEEDLE" in block
    assert "firstClick < 0 || secondClick >= 0" in block


def test_schema_21_marker_is_inserted_immediately_before_atomic_click():
    text = SCHEMA21.read_text(encoding="utf-8")
    start = text.index("_pr92Schema7AtomicAttachmentSubmitExpression = function")
    end = text.index("executeNativeTurn = async function", start)
    block = text[start:end]
    marker = "try { console.debug(${encodedMarker}); } catch {}"
    assert marker in block
    assert "expression.slice(0, firstClick)" in block
    assert "markerStatement" in block
    assert "expression.slice(firstClick)" in block

    schema7 = SCHEMA7.read_text(encoding="utf-8")
    validation = "if (Date.now() >= deadlineEpochMs)"
    click = "button.click();"
    assert schema7.index(validation, schema7.index("function _pr92Schema7AtomicAttachmentSubmitExpression")) < schema7.index(click)


def test_schema_21_has_no_prevalidation_marker_path():
    text = SCHEMA21.read_text(encoding="utf-8")
    assert "protectedSubmitArmAfterAllValidation: true" in text
    assert "preValidationSubmitArmPossible: false" in text
    assert '"AFTER_ALL_VALIDATION_IMMEDIATELY_BEFORE_BUTTON_CLICK"' in text

    schema20 = SCHEMA20.read_text(encoding="utf-8")
    assert "const _pr92Schema20PriorAtomicAttachmentSubmitExpression" in schema20


def test_schema_21_gate_preserves_schema_20_and_requires_boundary_fields():
    text = GATE21.read_text(encoding="utf-8")
    assert "SCHEMA = 21" in text
    assert "class ProductRichInputSchema21LiveProvider" in text
    assert 'legacy["schema"] = _v20.SCHEMA' in text
    assert "_v20._validate_support(legacy)" in text
    assert "protected_submit_arm_boundary" in text
    assert "protected_submit_arm_after_all_validation" in text
    assert "pre_validation_submit_arm_possible" in text
    assert "PRODUCT_WRITE_BUDGET = _v20.PRODUCT_WRITE_BUDGET" in text


def test_schema_21_support_probe_is_fifteenth_no_write_characterization_rpc():
    text = GATE21.read_text(encoding="utf-8")
    assert "Fifteenth characterization-only RPC: no text and no attachment paths." in text
    start = text.index("request_id = str(uuid.uuid4())")
    end = text.index("if response.get", start)
    request_block = text[start:end]
    assert '"characterizeRichInputSupport": True' in request_block
    assert '"text"' not in request_block
    assert '"attachmentPaths"' not in request_block
    assert "--acknowledge-live-writes" in text
    assert "performs exactly three product writes" in text
