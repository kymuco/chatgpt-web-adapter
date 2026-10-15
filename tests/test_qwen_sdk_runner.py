import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def runner(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "qwen_sdk_runner", Path(__file__).resolve().parents[1] / "qwen_sdk.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = Mock()
    client.send_text.return_value = SimpleNamespace(text="OK", conversation="chat")
    factory = Mock(return_value=client)
    monkeypatch.setattr(module, "QwenClient", factory)
    return module, factory, client


def test_default_browser_and_interactive_continuation(runner, monkeypatch):
    module, factory, client = runner
    messages = iter(["first", "second", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(messages))
    assert module.main([]) == 0
    factory.assert_called_once_with(transport="browser")
    assert client.send_text.call_args_list[0].kwargs["conversation"] is None
    assert client.send_text.call_args_list[1].kwargs["conversation"] == "chat"
    client.import_browser_auth.assert_not_called()


def test_explicit_http_is_labelled_experimental(runner, capsys):
    module, factory, client = runner
    assert module.main(["--transport", "http", "hello"]) == 0
    factory.assert_called_once_with(transport="http")
    assert "experimental" in capsys.readouterr().err
    client.send_text.assert_called_once()


def test_auth_import_without_transport_never_sends(runner):
    module, factory, client = runner
    assert module.main(["--import-auth"]) == 0
    factory.assert_called_once_with(transport="http")
    client.import_browser_auth.assert_called_once()
    client.send_text.assert_not_called()


def test_auth_failure_is_reported_without_traceback(runner, capsys):
    module, _, client = runner
    client.import_browser_auth.side_effect = RuntimeError(
        "QWEN_AUTH_SNAPSHOT_UNAVAILABLE"
    )
    assert module.main(["--import-auth"]) == 1
    assert "QWEN_AUTH_SNAPSHOT_UNAVAILABLE" in capsys.readouterr().err
    client.send_text.assert_not_called()


def test_browser_model_option_fails_before_send(runner):
    module, factory, _ = runner
    with pytest.raises(SystemExit):
        module.main(["--model", "some-model", "hello"])
    factory.assert_not_called()


def test_dom_renderer_rewrites_existing_terminal_text_not_append_revisions(capsys):
    from importlib.util import module_from_spec, spec_from_file_location
    from io import StringIO
    from os import terminal_size
    from pathlib import Path
    from unittest.mock import patch

    spec = spec_from_file_location(
        "qwen_sdk_live_renderer", Path(__file__).resolve().parents[1] / "qwen_sdk.py"
    )
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    class Tty(StringIO):
        def isatty(self):
            return True

    output = Tty()
    with patch.object(module.shutil, "get_terminal_size", return_value=terminal_size((100, 24))):
        renderer = module._QwenLiveAnswer(output)
        renderer.update("По состоянию на сезон 2026 года лидирует **Кими")
        renderer.update("По состоянию на сезон 2026 года лидирует Кими Антонелли")
        renderer.update(
            "По состоянию на сезон 2026 года лидирует Кими Антонелли, Mercedes."
        )
        renderer.finish(
            "По состоянию на сезон 2026 года лидирует Кими Антонелли, Mercedes."
        )
    out = output.getvalue()
    assert "\x1b[1F\x1b[J" in out
    assert "[Qwen revised answer]" not in out
    assert out.count("Mercedes.") == 1

    # When output is captured/piped, partial snapshots do not clutter logs.
    piped = StringIO()
    fallback = module._QwenLiveAnswer(piped)
    fallback.update("old partial")
    fallback.update("revised")
    fallback.finish("final")
    assert piped.getvalue() == "final\n"
