from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def _source(name: str) -> str:
    return (EXT / name).read_text(encoding="utf-8")


def test_picker_trigger_timeline_no_longer_owns_native_turn() -> None:
    identity = _source("service_worker_picker_trigger_identity_pr8_8.js")
    persistence = _source("service_worker_picker_trigger_persistence_pr8_8.js")

    assert "_pr88TriggerPriorExecuteNativeTurn" not in identity
    assert "executeNativeTurn =" not in persistence
    assert "PriorExecuteNativeTurn" not in persistence


def test_instant_failure_forensics_owner_preserves_picker_trigger_support_contract() -> None:
    owner = _source("service_worker_instant_popup_subtree_forensics_pr8_8.js")

    assert '"instant-failure-forensics"' in owner
    for token in (
        "pickerTriggerIdentitySupported",
        "clickActuationVerificationSupported",
        "perPollMenuMaterializationTimelineSupported",
        "falseOpenSurfaceDealiasingSupported",
        "triggerTimelinePersistenceSupported",
        "rawTriggerTextRedactionSupported",
    ):
        assert token in owner


def test_instant_failure_forensics_owner_preserves_picker_trigger_record_contract() -> None:
    owner = _source("service_worker_instant_popup_subtree_forensics_pr8_8.js")

    assert "await _pr88TriggerStoredRecord()" in owner
    assert "_pr88TriggerLeaseId(triggerStored.leaseId) === expectedLeaseId" in owner
    assert "delete triggerTimeline.leaseId" in owner
    assert "triggerTimeline.leaseIdExported = false" in owner
    assert "triggerTimelineRecordAvailable: triggerAvailable" in owner
    assert "triggerTimeline" in owner


def test_picker_trigger_helpers_are_loaded_before_diagnostic_dispatch_can_run() -> None:
    assembly = _source("service_worker_observability.js")
    owner = 'importScripts("service_worker_instant_popup_subtree_forensics_pr8_8.js");'
    identity = 'importScripts("service_worker_picker_trigger_identity_pr8_8.js");'
    persistence = 'importScripts("service_worker_picker_trigger_persistence_pr8_8.js");'

    assert owner in assembly and identity in assembly and persistence in assembly
    assert assembly.index(owner) < assembly.index(identity) < assembly.index(persistence)
