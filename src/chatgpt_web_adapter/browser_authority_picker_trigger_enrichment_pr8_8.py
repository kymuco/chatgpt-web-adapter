from __future__ import annotations

from .browser_authority_instant_failure_forensics_support_pr8_8 import _dict


def enrich_trigger_report(out, popup, timeline):
    topology = out.get("topology_summary")
    surface = out.get("picker_surface_forensics")
    if isinstance(topology, dict) and isinstance(surface, dict):
        popup_surfaces = _dict(surface.get("dom_topology")).get("popup_surfaces")
        popup_surfaces = popup_surfaces if isinstance(popup_surfaces, list) else []
        mode_bearing = sum(
            1 for item in popup_surfaces
            if isinstance(item, dict) and int(item.get("descendantKnownModeCount") or 0) > 0
        )
        legacy_open = surface.get("picker_surface_open") is True
        topology.update({
            "legacy_picker_surface_open": legacy_open,
            "generic_popup_surface_count": len(popup_surfaces),
            "mode_bearing_popup_surface_count": mode_bearing,
            "mode_bearing_picker_surface_open": mode_bearing > 0,
            "false_open_generic_only": legacy_open and mode_bearing == 0,
        })

    best = _dict(timeline.get("best_seen"))
    out["summary"].update({
        "in_failure_popup_subtree_captured": isinstance(popup, dict) and popup.get("capture_status") == "POPUP_SUBTREE_CAPTURED",
        "picker_trigger_timeline_captured": True,
        "picker_click_dispatch_completed": timeline.get("click_dispatch_completed") is True,
        "picker_materialization_outcome": timeline.get("materialization_outcome"),
        "picker_trigger_state_transition_observed": best.get("trigger_state_transition_observed") is True,
        "picker_mode_bearing_popup_ever_seen": best.get("max_mode_bearing_popup_surface_count", 0) > 0,
        "picker_false_open_generic_only_observed": best.get("false_open_generic_only_observed") is True,
        "picker_best_recognized_modes": best.get("recognized_modes", []),
    })
    return out
