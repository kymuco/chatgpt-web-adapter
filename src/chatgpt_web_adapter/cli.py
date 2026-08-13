from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .auth import DEFAULT_AUTH_FILE, load_auth_data
from .auth_browser import browser_login
from .auth_refresh import refresh_auth_session
from .auth_status import get_auth_status
from .browser_native_install import (
    EXTENSION_ID,
    browser_native_extension_dir,
    install_native_messaging_host,
)
from .browser_native_provider import BrowserNativeTurnProvider
from .client import ChatGPTWebClient
from .exceptions import WebChatAdapterError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chatgpt-web-adapter")
    commands = parser.add_subparsers(dest="command", required=True)

    auth = commands.add_parser("auth", help="manage reusable ChatGPT web authorization")
    auth_commands = auth.add_subparsers(dest="auth_command", required=True)

    def add_auth_file(command: argparse.ArgumentParser) -> None:
        command.add_argument("--auth-file", type=Path, default=DEFAULT_AUTH_FILE)

    login = auth_commands.add_parser("login", help="open a browser and save authorization")
    add_auth_file(login)
    login.add_argument("--profile-dir", type=Path)
    login.add_argument("--timeout", type=float, default=300.0)
    login.add_argument("--browser-executable-path", type=Path)
    login.add_argument(
        "--force",
        action="store_true",
        help="ignore saved auth and require a fresh interactive browser login",
    )

    status = auth_commands.add_parser("status", help="show authorization health")
    add_auth_file(status)
    status.add_argument("--profile-dir", type=Path)

    refresh = auth_commands.add_parser("refresh", help="refresh tokens without browser login")
    add_auth_file(refresh)

    browser_native = commands.add_parser(
        "browser-native",
        help="manage the persistent browser-native ChatGPT turn bridge",
    )
    browser_native_commands = browser_native.add_subparsers(
        dest="browser_native_command",
        required=True,
    )
    native_install = browser_native_commands.add_parser(
        "install",
        help="register the Native Messaging host for the packaged extension",
    )
    native_install.add_argument("--extension-id", default=EXTENSION_ID)
    native_install.add_argument("--host-executable", type=Path)
    browser_native_commands.add_parser(
        "status",
        help="show whether the Native Messaging bridge and extension are connected",
    )
    browser_native_commands.add_parser(
        "extension-dir",
        help="print the packaged unpacked-extension directory",
    )
    return parser


def _run_auth(args: argparse.Namespace) -> int:
    if args.auth_command == "login":
        result = browser_login(
            args.auth_file,
            profile_dir=args.profile_dir,
            timeout=args.timeout,
            browser_executable_path=args.browser_executable_path,
            reuse_existing_auth=not args.force,
        )
        print(f"Authorization saved to {result.auth_file}")
        print(f"Persistent browser profile: {result.profile_dir}")
        return 0
    if args.auth_command == "status":
        status = get_auth_status(args.auth_file, profile_dir=args.profile_dir)
        print(
            json.dumps(
                {
                    "auth_file": str(status.auth_file),
                    "file_exists": status.file_exists,
                    "access_token_present": status.access_token_present,
                    "access_token_expires_at": (
                        status.access_token_expires_at.isoformat()
                        if status.access_token_expires_at is not None
                        else None
                    ),
                    "access_token_needs_refresh": status.access_token_needs_refresh,
                    "session_cookie_present": status.session_cookie_present,
                    "session_expires_at": status.session_expires_at,
                    "browser_cookie_count": status.browser_cookie_count,
                    "browser_profile_dir": str(status.browser_profile_dir),
                    "browser_profile_exists": status.browser_profile_exists,
                },
                indent=2,
            )
        )
        return 0 if status.file_exists else 1
    if args.auth_command == "refresh":
        auth = load_auth_data(args.auth_file, allow_expired_session_refresh=True)
        client = ChatGPTWebClient(
            auth=auth,
            auth_file=args.auth_file,
            auto_refresh_auth=False,
        )
        result = refresh_auth_session(client, auth_file=args.auth_file)
        print(
            json.dumps(
                {
                    "status_code": result.status_code,
                    "session_token_rotated": result.session_token_rotated,
                    "persisted": result.persisted,
                },
                indent=2,
            )
        )
        return 0
    return 2


def _run_browser_native(args: argparse.Namespace) -> int:
    if args.browser_native_command == "install":
        result = install_native_messaging_host(
            extension_id=args.extension_id,
            host_executable=args.host_executable,
        )
        print(
            json.dumps(
                {
                    "host_name": result.host_name,
                    "extension_id": result.extension_id,
                    "extension_dir": str(result.extension_dir),
                    "host_manifest": str(result.host_manifest),
                    "host_executable": str(result.host_executable),
                },
                indent=2,
            )
        )
        return 0
    if args.browser_native_command == "extension-dir":
        print(browser_native_extension_dir())
        return 0
    if args.browser_native_command == "status":
        status = BrowserNativeTurnProvider().status()
        print(
            json.dumps(
                {
                    "available": status.available,
                    "extension_connected": status.extension_connected,
                    "host_pid": status.host_pid,
                    "extension_id": status.extension_id,
                    "runtime_tab_id": status.runtime_tab_id,
                },
                indent=2,
            )
        )
        return 0 if status.available and status.extension_connected else 1
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "auth":
            return _run_auth(args)
        if args.command == "browser-native":
            return _run_browser_native(args)
    except (WebChatAdapterError, OSError, ValueError) as error:
        print(f"error: {error}")
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
