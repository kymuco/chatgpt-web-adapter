from __future__ import annotations

from types import SimpleNamespace

import chatgpt_web_adapter.browser_owned_write_runtime as subject


class FakeProvider:
    def send_text(self, *args, **kwargs):
        raise AssertionError("low-level provider should be called through send_browser_native")

    def status(self):
        return subject.BrowserNativeBridgeStatus(
            available=True,
            extension_connected=True,
            runtime_tab_id=None,
        )


class FakeClient:
    _browser_native_turn_provider = None

    def get_status(self, conversation):
        return SimpleNamespace(status="completed")


def _runtime():
    return subject.BrowserOwnedProductWriteRuntime(FakeClient(), provider=FakeProvider())


def test_observed_send_captures_created_background_tab(monkeypatch) -> None:
    expected = SimpleNamespace(text="ok")

    def fake_send(*args, **kwargs):
        kwargs["on_event"](
            {
                "type": "browser_native_write_completed",
                "runtime_tab_id": 17,
                "runtime_tab_preexisting": False,
                "runtime_tab_created_for_turn": True,
                "tab_was_active_at_write_start": False,
                "tab_active_after_write": False,
                "tab_activated_during_turn": False,
                "foreground_activation_observed": False,
            }
        )
        return expected

    monkeypatch.setattr(subject, "send_browser_native", fake_send)
    execution = _runtime().send_text_observed("hello")
    assert execution.response is expected
    assert execution.observation.write_event_observed is True
    assert execution.observation.runtime_tab_id == 17
    assert execution.observation.runtime_tab_preexisting is False
    assert execution.observation.runtime_tab_created_for_turn is True
    assert execution.observation.foreground_activation_observed is False


def test_observed_send_preserves_old_extension_metadata_as_unknown(monkeypatch) -> None:
    expected = SimpleNamespace(text="ok")

    def fake_send(*args, **kwargs):
        kwargs["on_event"]({"type": "browser_native_write_completed"})
        return expected

    monkeypatch.setattr(subject, "send_browser_native", fake_send)
    observation = _runtime().send_text_observed("hello").observation
    assert observation.write_event_observed is True
    assert observation.runtime_tab_preexisting is None
    assert observation.runtime_tab_created_for_turn is None
    assert observation.foreground_activation_observed is None


def test_observed_send_reports_missing_write_event_without_false_negative(monkeypatch) -> None:
    expected = SimpleNamespace(text="ok")
    monkeypatch.setattr(subject, "send_browser_native", lambda *args, **kwargs: expected)
    observation = _runtime().send_text_observed("hello").observation
    assert observation.write_event_observed is False
    assert observation.foreground_activation_observed is None


def test_governance_disambiguates_process_and_tab_ownership() -> None:
    policy = _runtime().governance()
    assert policy["browser_process_launch_owned_by_runtime"] is False
    assert policy["runtime_tab_creation_owned_by_extension"] is True
    assert policy["runtime_tab_creation_on_demand"] is True
    assert policy["runtime_tab_foreground_activation_requested"] is False
    assert policy["browser_launch_owned_by_runtime"] is False
