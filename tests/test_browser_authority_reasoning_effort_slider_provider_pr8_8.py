from chatgpt_web_adapter.browser_authority_reasoning_effort_slider_pr8_8 import ReasoningEffortSliderProvider


def test_provider_parses_support(monkeypatch):
    p = ReasoningEffortSliderProvider()
    monkeypatch.setattr(p, "_characterization_rpc", lambda payload, timeout: {
        "reasoningEffortSliderSupported": True,
        "reasoningEffortSliderSchemaVersion": 1,
        "retainedExistingTabProbeSupported": True,
        "sliderTopologySupported": True,
        "discreteStepMappingSupported": True,
        "quickAdvancedDimensionSeparationSupported": True,
        "uiNavigationOptInSupported": True,
        "selectionControlClickForbidden": True,
        "conversationWriteGuardSupported": True,
        "rawTextRedactionSupported": True,
        "leaseIdExported": False,
        "zeroProductWrites": True,
        "automaticRetry": False,
    })
    s = p.reasoning_effort_slider_support()
    assert s["supported"] and s["schema"] == 1
    assert s["slider_topology_supported"] and s["discrete_step_mapping_supported"]
    assert s["quick_advanced_dimension_separation_supported"]
    assert s["selection_control_click_forbidden"]
    assert not s["lease_id_exported"] and not s["automatic_retry"]


def test_provider_parses_three_step_slider_and_advanced_dimensions(monkeypatch):
    p = ReasoningEffortSliderProvider()
    monkeypatch.setattr(p, "_characterization_rpc", lambda payload, timeout: {
        "conversationId": "c1", "runtimeTabId": 7, "runtimeTabIdAfter": 7,
        "leaseIdPresent": True, "rawUrlExported": False, "rawTextExported": False,
        "rawHtmlExported": False, "leaseIdExported": False, "zeroProductWrites": True,
        "conversationWriteCount": 0, "chatgptMutationCount": 0,
        "uiNavigationAcknowledged": True, "quickOpenClickPerformed": True,
        "advancedClickPerformed": True, "selectionControlClickPerformed": False,
        "quickTopology": {
            "surfaceFound": True, "genericSurfaceCount": 3, "modeBearingSurfaceCount": 1,
            "sliderSurfaceCount": 1, "currentEffortCandidateCount": 1,
            "currentEffortControl": {"tag":"BUTTON","effortMode":"HIGH","rect":{"x":1,"y":2,"width":3,"height":4}},
            "sliders": [{"index":0,"tag":"DIV","role":"slider","orientation":"horizontal","ariaValueMin":0,"ariaValueMax":2,"ariaValueNow":2,"ariaValueTextMode":"HIGH","rect":{"x":0,"y":0,"width":300,"height":20}}],
            "effortMarks": [],
            "discreteStepMapping": [
                {"mode":"INSTANT","rank":0,"normalizedPosition":0},
                {"mode":"MEDIUM","rank":1,"normalizedPosition":0.5},
                {"mode":"HIGH","rank":2,"normalizedPosition":1},
            ],
            "completeThreeStepMapping": True, "advancedButtonCount": 1,
            "advancedButton": {"tag":"BUTTON","dimension":"ADVANCED","rect":{"x":1,"y":1,"width":10,"height":10}},
        },
        "advancedTopology": {
            "surfaceFound": True, "candidateSurfaceCount": 1,
            "dimensionControls": [{"tag":"BUTTON","dimension":"MODEL"},{"tag":"BUTTON","dimension":"EFFORT"},{"tag":"BUTTON","dimension":"BACK"}],
            "modelControlCount": 1, "effortControlCount": 1, "backControlCount": 1,
            "dimensionsSeparated": True,
            "visibleModelValues": ["GPT_5_6_SOL","GPT_5_5","O3"],
            "visibleEffortValues": ["INSTANT","MEDIUM","HIGH"],
        },
    })
    r = p.reasoning_effort_slider_topology("c1", expected_runtime_tab_id=7, open_quick_picker=True, inspect_advanced_surface=True, allow_ui_navigation=True)
    assert r["quick_topology"]["complete_three_step_mapping"] is True
    assert [x["mode"] for x in r["quick_topology"]["discrete_step_mapping"]] == ["INSTANT","MEDIUM","HIGH"]
    assert r["advanced_topology"]["dimensions_separated"] is True
    assert r["selection_control_click_performed"] is False
