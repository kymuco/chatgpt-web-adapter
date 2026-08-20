from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

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
from .conversation_snapshot import snapshot_conversation
from .exceptions import WebChatAdapterError
from .product_runtime import (
    DEFAULT_PRODUCT_TRANSPORT,
    SUPPORTED_PRODUCT_TRANSPORTS,
    assemble_product_runtime,
)
from .standalone_send import (
    DEFAULT_STANDALONE_MODEL_PROFILE,
    STANDALONE_MODEL_PROFILES,
    RevisionSafeTerminalRenderer,
    normalize_standalone_model_profile,
)


def _execution_payload(execution: Any) -> dict[str, Any]:
    response = execution.response
    provenance = execution.provenance
    return {
        "transport": execution.transport,
        "ok": True,
        "text": response.text,
        "title": response.title,
        "conversation_id": response.conversation.conversation_id,
        "message_id": response.conversation.message_id,
        "finish_reason": response.conversation.finish_reason,
        "observed_model": response.request.observed_model,
        "backend_status": response.metrics.backend_status,
        "runtime_observation": execution.observation.to_dict(),
        "provenance": provenance.to_dict() if provenance is not None else None,
    }


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

    snapshot = commands.add_parser(
        "snapshot",
        help="write a deterministic user/assistant conversation snapshot",
    )
    add_auth_file(snapshot)
    snapshot.add_argument("conversation", help="raw conversation id or ChatGPT conversation URL")
    snapshot.add_argument(
        "--name",
        default="conversation",
        help="file-name prefix; defaults to 'conversation'",
    )
    snapshot.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="directory for snapshot files",
    )
    snapshot.add_argument(
        "--index",
        type=int,
        help="explicit positive snapshot number; otherwise the next number is selected",
    )
    snapshot.add_argument("--timeout", type=float, default=120.0)
    snapshot.add_argument(
        "--context-only",
        action="store_true",
        help="skip the raw conversation-payload backup",
    )

    send = commands.add_parser(
        "send",
        help="send one ordinary ChatGPT turn; defaults to DEEP / product HIGH",
    )
    add_auth_file(send)
    send.add_argument("text")
    send.add_argument("--conversation")
    send.add_argument(
        "--transport",
        choices=SUPPORTED_PRODUCT_TRANSPORTS,
        default=DEFAULT_PRODUCT_TRANSPORT,
        help="explicit product transport; no automatic fallback is performed",
    )
    send.add_argument(
        "--profile",
        type=normalize_standalone_model_profile,
        choices=STANDALONE_MODEL_PROFILES,
        default=DEFAULT_STANDALONE_MODEL_PROFILE,
        help="semantic model profile; default DEEP maps to proven product HIGH",
    )
    send.add_argument("--timeout", type=float, default=150.0)
    send.add_argument("--poll-interval", type=float, default=0.5)
    output_mode = send.add_mutually_exclusive_group()
    output_mode.add_argument(
        "--stream",
        action="store_true",
        help="render revision-safe assistant text while generation is in progress",
    )
    output_mode.add_argument(
        "--json",
        action="store_true",
        help="print the structured observed execution instead of plain text",
    )

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

    runtime = commands.add_parser(
        "runtime",
        help="use the production ordinary-ChatGPT product runtime",
    )
    runtime_commands = runtime.add_subparsers(dest="runtime_command", required=True)

    def add_runtime_common(command: argparse.ArgumentParser) -> None:
        add_auth_file(command)
        command.add_argument(
            "--transport",
            choices=SUPPORTED_PRODUCT_TRANSPORTS,
            default=DEFAULT_PRODUCT_TRANSPORT,
            help="explicit product transport; no automatic fallback is performed",
        )
        command.add_argument("--conversation")

    runtime_status = runtime_commands.add_parser(
        "status",
        help="show production runtime readiness for a new or existing conversation",
    )
    add_runtime_common(runtime_status)

    runtime_send = runtime_commands.add_parser(
        "send",
        help="send one ordinary ChatGPT product turn through the production runtime",
    )
    add_runtime_common(runtime_send)
    runtime_send.add_argument("text")
    runtime_send.add_argument("--timeout", type=float, default=150.0)
    runtime_send.add_argument("--poll-interval", type=float, default=0.5)
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


def _run_snapshot(args: argparse.Namespace) -> int:
    client = ChatGPTWebClient(
        auth_file=args.auth_file,
        timeout=args.timeout,
    )
    result = snapshot_conversation(
        client,
        args.conversation,
        output_dir=args.output_dir,
        name=args.name,
        index=args.index,
        include_raw_payload=not args.context_only,
    )

    print(f"context:     {result.context_path.resolve()}")
    if result.raw_payload_path is not None:
        print(f"raw payload: {result.raw_payload_path.resolve()}")
    print(f"messages:    {result.message_count}")
    return 0


def _run_send(args: argparse.Namespace) -> int:
    runtime = assemble_product_runtime(
        transport=args.transport,
        auth_file=args.auth_file,
    )
    renderer = RevisionSafeTerminalRenderer() if args.stream else None
    execution = runtime.send_text_observed(
        args.text,
        conversation=args.conversation,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        on_event=renderer.on_event if renderer is not None else None,
        model_profile=args.profile,
    )

    if renderer is not None:
        renderer.finish(execution.response.text)
    elif args.json:
        print(json.dumps(_execution_payload(execution), indent=2, ensure_ascii=False))
    else:
        print(execution.response.text)
    return 0


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


def _run_runtime(args: argparse.Namespace) -> int:
    runtime = assemble_product_runtime(
        transport=args.transport,
        auth_file=args.auth_file,
    )
    if args.runtime_command == "status":
        health = runtime.health(args.conversation)
        capabilities = runtime.capabilities()
        print(
            json.dumps(
                {
                    "transport": runtime.transport,
                    "health": health.to_dict(),
                    "capabilities": capabilities.to_dict(),
                    "governance": runtime.governance(),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if health.ready else 1
    if args.runtime_command == "send":
        execution = runtime.send_text_observed(
            args.text,
            conversation=args.conversation,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
        )
        print(json.dumps(_execution_payload(execution), indent=2, ensure_ascii=False))
        return 0
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "auth":
            return _run_auth(args)
        if args.command == "snapshot":
            return _run_snapshot(args)
        if args.command == "send":
            return _run_send(args)
        if args.command == "browser-native":
            return _run_browser_native(args)
        if args.command == "runtime":
            return _run_runtime(args)
    except (WebChatAdapterError, OSError, ValueError) as error:
        print(f"error: {error}")
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
