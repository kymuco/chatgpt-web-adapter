from types import SimpleNamespace

from chatgpt_web_adapter.browser_authority_reasoning_effort_slider_live_pr8_8 import ReasoningEffortSliderRunner


class Provider:
    def reasoning_effort_slider_support(self):
        return {
            "supported": True, "schema": 1, "retained_existing_tab_probe_supported": True,
            "slider_topology_supported": True, "discrete_step_mapping_supported": True,
            "quick_advanced_dimension_separation_supported": True, "ui_navigation_opt_in_supported": True,
            "selection_control_click_forbidden": True, "conversation_write_guard_supported": True,
            "raw_text_redaction_supported": True, "lease_id_exported": False,
            "zero_product_writes": True, "automatic_retry": False,
        }
    def characterization_status(self):
        return SimpleNamespace(runtime_tab_id=9, lease_id_present=True, to_dict=lambda: {"runtime_tab_id":9,"lease_id_present":True})
    def reasoning_effort_slider_topology(self, *args, **kwargs):
        return {
            "runtime_tab_id":9,"runtime_tab_id_after":9,"lease_id_present":True,
            "zero_product_writes":True,"conversation_write_count":0,"selection_control_click_performed":False,
            "raw_url_exported":False,"raw_text_exported":False,"raw_html_exported":False,"lease_id_exported":False,
            "quick_topology":{"surface_found":True,"sliders":[{}],"complete_three_step_mapping":True,"advanced_button_count":1,"discrete_step_mapping":[{"mode":"INSTANT"},{"mode":"MEDIUM"},{"mode":"HIGH"}],"current_effort_control":{}},
            "advanced_topology":{"surface_found":True,"model_control_count":1,"effort_control_count":1,"dimensions_separated":True,"visible_model_values":[],"visible_effort_values":[]},
        }


class Runtime:
    def health(self, conversation):
        return SimpleNamespace(ready=True, canonical_status="completed", to_dict=lambda: {"ready":True,"canonical_status":"completed"})


def test_runner_accepts_zero_write_slider_and_separated_dimensions():
    r = ReasoningEffortSliderRunner(Runtime(), provider=Provider()).run(
        conversation="c1", open_quick_picker=True, inspect_advanced_surface=True, allow_ui_navigation=True
    )
    assert r["ok"] is True
    assert r["product_write_budget"] == 0 and r["write_attempts"] == 0
    assert r["summary"]["three_step_mapping_proven"] is True
    assert r["summary"]["model_effort_dimensions_separated"] is True
    assert r["summary"]["selection_control_click_performed"] is False
