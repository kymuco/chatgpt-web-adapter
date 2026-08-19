from __future__ import annotations

from .browser_authority_policy_replication_pr8_8 import _observation_record, _provenance_record
from .browser_authority_instant_failure_forensics_support_pr8_8 import _str


def characterize_success(runner, report, execution, conversation: str, forensics_timeout: float, phase: list[str]):
    report["write_completions"] = 1
    phase[0] = "unexpected_success_characterization"
    observation = _observation_record(execution)
    report["successful_write"] = {
        "provenance": _provenance_record(execution),
        "observation": observation,
    }
    lease_id = _str(observation.get("browser_authority_lease_id"))
    if lease_id:
        try:
            report["instant_selection"] = runner.provider.instant_selection_for_lease(lease_id)
        except Exception as error:
            report["instant_selection_read_error"] = runner._failure(error)

    status = runner.provider.characterization_status()
    report["final_authority_status"] = status.to_dict()
    if isinstance(status.runtime_tab_id, int):
        try:
            report["route_forensics"] = runner.provider.retained_route_identity_forensics(
                conversation,
                expected_runtime_tab_id=status.runtime_tab_id,
                timeout=min(10.0, forensics_timeout),
            )
        except Exception as error:
            report["route_forensics_error"] = runner._failure(error)

    report["write_outcome"] = "SUCCEEDED"
    report["target_failure_reproduced"] = False
    report["summary"] = {
        "single_live_attempt_completed": True,
        "target_instant_option_failure_reproduced": False,
        "write_succeeded": True,
        "additional_product_writes_after_first_attempt": 0,
        "retained_tab_close_performed": False,
        "automatic_write_retry_attempted": False,
        "write_budget_respected": True,
    }
    report["ok"] = True
    return report
