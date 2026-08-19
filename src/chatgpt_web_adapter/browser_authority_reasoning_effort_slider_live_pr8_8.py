from __future__ import annotations

import argparse
import json
from pathlib import Path

from .browser_authority_reasoning_effort_slider_pr8_8 import ReasoningEffortSliderProvider, SCHEMA
from .client import ChatGPTWebClient
from .product_runtime import assemble_product_runtime


def _require(ok, message):
    if not ok:
        raise RuntimeError(message)


class ReasoningEffortSliderRunner:
    def __init__(self, runtime, *, provider):
        self.runtime = runtime
        self.provider = provider

    def run(self, *, conversation, open_quick_picker=False, inspect_advanced_surface=False, allow_ui_navigation=False, timeout=15.0):
        report = {
            "ok": False,
            "pr": "PR8.8",
            "probe_context": "reasoning_effort_slider_topology_dimension_separation_zero_product_write",
            "conversation": conversation,
            "product_write_budget": 0,
            "write_attempts": 0,
            "write_completions": 0,
            "automatic_write_retry": False,
            "ui_navigation_click_budget": int(bool(open_quick_picker)) + int(bool(inspect_advanced_surface)),
            "failure_phase": None,
            "failure": None,
        }
        phase = "support_preflight"
        try:
            support = self.provider.reasoning_effort_slider_support()
            report["support"] = support
            _require(support["supported"] and support["schema"] == SCHEMA, "PR8_8_REASONING_EFFORT_EXTENSION_RELOAD_REQUIRED")
            for key in (
                "retained_existing_tab_probe_supported", "slider_topology_supported",
                "discrete_step_mapping_supported", "quick_advanced_dimension_separation_supported",
                "ui_navigation_opt_in_supported", "selection_control_click_forbidden",
                "conversation_write_guard_supported", "raw_text_redaction_supported", "zero_product_writes",
            ):
                _require(support[key] is True, "PR8_8_REASONING_EFFORT_SUPPORT_INCOMPLETE")
            _require(not support["lease_id_exported"] and not support["automatic_retry"], "PR8_8_REASONING_EFFORT_GOVERNANCE_CHANGED")

            phase = "retained_authority_preflight"
            status = self.provider.characterization_status()
            report["initial_authority_status"] = status.to_dict()
            _require(isinstance(status.runtime_tab_id, int), "PR8_8_REASONING_EFFORT_RETAINED_TAB_REQUIRED")
            _require(status.lease_id_present is True, "PR8_8_REASONING_EFFORT_LEASE_REQUIRED")
            tab_id = status.runtime_tab_id
            health = self.runtime.health(conversation)
            report["initial_runtime_health"] = health.to_dict()
            _require(health.ready is True and health.canonical_status == "completed", "PR8_8_REASONING_EFFORT_CANONICAL_NOT_STABLE")

            phase = "topology_characterization"
            topology = self.provider.reasoning_effort_slider_topology(
                conversation,
                expected_runtime_tab_id=tab_id,
                open_quick_picker=open_quick_picker,
                inspect_advanced_surface=inspect_advanced_surface,
                allow_ui_navigation=allow_ui_navigation,
                timeout=timeout,
            )
            report["topology"] = topology
            _require(topology["runtime_tab_id"] == tab_id == topology["runtime_tab_id_after"], "PR8_8_REASONING_EFFORT_TAB_CHANGED")
            _require(topology["lease_id_present"] is True, "PR8_8_REASONING_EFFORT_LEASE_DISAPPEARED")
            _require(topology["zero_product_writes"] and topology["conversation_write_count"] == 0, "PR8_8_REASONING_EFFORT_ZERO_WRITE_BOUNDARY_VIOLATED")
            _require(topology["selection_control_click_performed"] is False, "PR8_8_REASONING_EFFORT_SELECTION_CONTROL_CLICKED")
            _require(not topology["raw_url_exported"] and not topology["raw_text_exported"] and not topology["raw_html_exported"] and not topology["lease_id_exported"], "PR8_8_REASONING_EFFORT_PRIVACY_BOUNDARY_VIOLATED")

            quick = topology["quick_topology"]
            _require(quick["surface_found"] is True, "PR8_8_REASONING_EFFORT_QUICK_SURFACE_NOT_FOUND")
            _require(len(quick["sliders"]) >= 1, "PR8_8_REASONING_EFFORT_SLIDER_NOT_FOUND")
            _require(quick["complete_three_step_mapping"] is True, "PR8_8_REASONING_EFFORT_THREE_STEP_MAPPING_NOT_PROVEN")
            _require(quick["advanced_button_count"] == 1, "PR8_8_REASONING_EFFORT_ADVANCED_CONTROL_NOT_UNIQUE")

            advanced = topology["advanced_topology"]
            if inspect_advanced_surface:
                _require(isinstance(advanced, dict) and advanced["surface_found"], "PR8_8_REASONING_EFFORT_ADVANCED_SURFACE_NOT_FOUND")
                _require(advanced["model_control_count"] == 1 and advanced["effort_control_count"] == 1, "PR8_8_REASONING_EFFORT_DIMENSION_CONTROLS_NOT_UNIQUE")
                _require(advanced["dimensions_separated"] is True, "PR8_8_REASONING_EFFORT_DIMENSIONS_NOT_SEPARATED")

            phase = "post_probe_recheck"
            final_status = self.provider.characterization_status()
            report["final_authority_status"] = final_status.to_dict()
            _require(final_status.runtime_tab_id == tab_id and final_status.lease_id_present is True, "PR8_8_REASONING_EFFORT_AUTHORITY_CHANGED")
            post = self.runtime.health(conversation)
            report["final_runtime_health"] = post.to_dict()
            _require(post.ready is True and post.canonical_status == "completed", "PR8_8_REASONING_EFFORT_CANONICAL_CHANGED")

            report["summary"] = {
                "quick_surface_proven": True,
                "slider_count": len(quick["sliders"]),
                "three_step_mapping_proven": True,
                "discrete_step_mapping": quick["discrete_step_mapping"],
                "current_effort_control": quick["current_effort_control"],
                "advanced_control_unique": True,
                "advanced_surface_inspected": bool(inspect_advanced_surface),
                "model_effort_dimensions_separated": bool(advanced and advanced["dimensions_separated"]),
                "visible_model_values": advanced["visible_model_values"] if advanced else [],
                "visible_effort_values": advanced["visible_effort_values"] if advanced else [],
                "selection_control_click_performed": False,
                "conversation_writes": 0,
                "automatic_retry_attempted": False,
            }
            report["ok"] = True
            return report
        except Exception as error:
            report["failure_phase"] = phase
            report["failure"] = {"type": type(error).__name__, "message": str(error), "automatic_retry_attempted": False}
            return report


def main(argv=None):
    p = argparse.ArgumentParser(description="PR8.8 reasoning-effort slider topology and quick/advanced dimension separation")
    p.add_argument("--conversation", required=True)
    p.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--open-quick-picker", action="store_true")
    p.add_argument("--inspect-advanced-surface", action="store_true")
    p.add_argument("--allow-ui-navigation", action="store_true")
    args = p.parse_args(argv)
    if (args.open_quick_picker or args.inspect_advanced_surface) and not args.allow_ui_navigation:
        p.error("--allow-ui-navigation is required for picker/Advanced navigation clicks")
    client = ChatGPTWebClient(auth_file=args.auth_file, auto_refresh_auth=True, auto_login=False, auto_sentinel=False)
    provider = ReasoningEffortSliderProvider()
    runtime = assemble_product_runtime(client=client, provider=provider)
    report = ReasoningEffortSliderRunner(runtime, provider=provider).run(
        conversation=args.conversation,
        open_quick_picker=args.open_quick_picker,
        inspect_advanced_surface=args.inspect_advanced_surface,
        allow_ui_navigation=args.allow_ui_navigation,
        timeout=args.timeout,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
