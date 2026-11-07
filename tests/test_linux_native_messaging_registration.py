"""Offline Linux native-host registration checks; no browser or user session."""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest

from chatgpt_web_adapter import browser_native_install, qwen_native
from chatgpt_web_adapter.browser_native_protocol import HOST_NAME as CWA_HOST_NAME

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="Linux per-user Native Messaging locations"
)


def _assert_manifest(
    path: Path, *, host_name: str, executable: Path, extension_id: str
):
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {
        "name": host_name,
        "description": (
            "Independent Qwen bridge"
            if host_name == qwen_native.HOST_NAME
            else "ChatGPT Web Adapter browser-native bridge"
        ),
        "path": str(executable.resolve()),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_linux_manifest_paths_use_xdg_configuration(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("CHROME_CONFIG_HOME", raising=False)
    config = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    paths = browser_native_install.linux_native_messaging_manifest_paths("test.host")
    assert paths == (
        config / "google-chrome" / "NativeMessagingHosts" / "test.host.json",
        config / "chromium" / "NativeMessagingHosts" / "test.host.json",
    )


def test_linux_manifest_paths_prefer_chrome_config_home(monkeypatch, tmp_path: Path):
    xdg = tmp_path / "xdg"
    chrome = tmp_path / "chrome-config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.setenv("CHROME_CONFIG_HOME", str(chrome))

    paths = browser_native_install.linux_native_messaging_manifest_paths("test.host")
    assert paths == (
        chrome / "google-chrome" / "NativeMessagingHosts" / "test.host.json",
        chrome / "chromium" / "NativeMessagingHosts" / "test.host.json",
    )

    # An explicitly supplied destination remains authoritative.
    explicit = browser_native_install.linux_native_messaging_manifest_paths(
        "test.host", config_home=xdg
    )
    assert explicit == (
        xdg / "google-chrome" / "NativeMessagingHosts" / "test.host.json",
        xdg / "chromium" / "NativeMessagingHosts" / "test.host.json",
    )


def test_linux_invalid_chrome_override_falls_back_to_xdg(monkeypatch, tmp_path: Path):
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.setenv("CHROME_CONFIG_HOME", "relative/not-accepted")

    paths = browser_native_install.linux_native_messaging_manifest_paths("test.host")
    assert paths[0] == (
        xdg / "google-chrome" / "NativeMessagingHosts" / "test.host.json"
    )


def test_browser_state_persists_beyond_xdg_runtime_dir(monkeypatch, tmp_path: Path):
    from chatgpt_web_adapter.browser_native_protocol import (
        default_browser_native_state_dir,
    )

    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    expected = tmp_path / "state" / "chatgpt-web-adapter"
    assert default_browser_native_state_dir() == expected / "browser-native"
    assert qwen_native.state_dir() == expected / "qwen-native"


def test_chatgpt_installer_registers_both_linux_browsers(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("CHROME_CONFIG_HOME", raising=False)
    config = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setattr(
        browser_native_install,
        "default_browser_native_state_dir",
        lambda: tmp_path / "state" / "browser-native",
    )
    executable = tmp_path / "bin" / "chatgpt-web-adapter-native-host"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\n", encoding="utf-8")

    result = browser_native_install.install_native_messaging_host(
        host_executable=executable
    )

    paths = browser_native_install.linux_native_messaging_manifest_paths(CWA_HOST_NAME)
    assert result.host_manifest == paths[0]
    assert result.host_executable == executable.resolve()
    for path in paths:
        _assert_manifest(
            path,
            host_name=CWA_HOST_NAME,
            executable=executable,
            extension_id=browser_native_install.EXTENSION_ID,
        )
    assert result.extension_dir.is_dir()


def test_qwen_installer_registers_isolated_linux_host(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("CHROME_CONFIG_HOME", raising=False)
    config = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setattr(qwen_native, "state_dir", lambda: tmp_path / "qwen-native")
    executable = tmp_path / "venv" / "bin" / "qwen-web-adapter-native-host"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(
        qwen_native.sys, "executable", str(executable.parent / "python")
    )
    extension_id = "abcdefghijklmnopabcdefghijklmnop"
    monkeypatch.setattr(
        qwen_native.sys,
        "argv",
        ["qwen-native", "--extension-id", extension_id],
    )

    qwen_native.main()

    paths = browser_native_install.linux_native_messaging_manifest_paths(
        qwen_native.HOST_NAME
    )
    for path in paths:
        _assert_manifest(
            path,
            host_name=qwen_native.HOST_NAME,
            executable=executable,
            extension_id=extension_id,
        )
    assert (tmp_path / "qwen-native" / "extension" / "manifest.json").is_file()
    for path in browser_native_install.linux_native_messaging_manifest_paths(
        CWA_HOST_NAME
    ):
        assert not path.exists()
