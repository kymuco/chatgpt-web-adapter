from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from . import cli as legacy_cli
from .auth import DEFAULT_AUTH_FILE
from .product_runtime import (
    DEFAULT_PRODUCT_TRANSPORT,
    SUPPORTED_PRODUCT_TRANSPORTS,
    assemble_product_runtime,
)
from .types import ConversationRef

CLI_CONTRACT_SCHEMA = 1
EXIT_OK = 0
EXIT_UNAVAILABLE = 1
EXIT_USAGE = 2
EXIT_OPERATION_FAILED = 3
EXIT_RECONCILIATION_REQUIRED = 4

PRODUCT_NATIVE_MODEL_PROFILES: tuple[str, ...] = ("INSTANT", "MEDIUM", "HIGH")
SEMANTIC_MODEL_PROFILES: tuple[str, ...] = ("FAST", "BALANCED", "DEEP")
PUBLIC_MODEL_PROFILES: tuple[str, ...] = (
    *PRODUCT_NATIVE_MODEL_PROFILES,
    *SEMANTIC_MODEL_PROFILES,
)
PRODUCT_NATIVE_TO_SEMANTIC: dict[str, str] = {
    "INSTANT": "FAST",
    "MEDIUM": "BALANCED",
    "HIGH": "DEEP",
}
SEMANTIC_TO_PRODUCT_NATIVE: dict[str, str] = {
    semantic: product
    for product, semantic in PRODUCT_NATIVE_TO_SEMANTIC.items()
}
DEFAULT_PUBLIC_MODEL_PROFILE = "HIGH"


def normalize_public_model_profile(value: str) -> str:
    """Normalize product-native or semantic profile names to CWA's proven semantic key."""

    if not isinstance(value, str):
        raise TypeError("profile must be a string")
    normalized = value.strip().upper()
    if normalized in PRODUCT_NATIVE_TO_SEMANTIC:
        return PRODUCT_NATIVE_TO_SEMANTIC[normalized]
    if normalized in SEMANTIC_MODEL_PROFILES:
        return normalized
    supported = ", ".join(PUBLIC_MODEL_PROFILES)
    raise ValueError(f"unsupported profile {value!r}; expected one of: {supported}")


def product_native_model_profile(value: str) -> str:
    semantic = normalize_public_model_profile(value)
    return SEMANTIC_TO_PRODUCT_NATIVE[semantic]


def _argparse_model_profile(value: str) -> str:
    try:
        return normalize_public_model_profile(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def model_profile_contract() -> dict[str, Any]:
    return {
        "default": DEFAULT_PUBLIC_MODEL_PROFILE,
        "product_native": list(PRODUCT_NATIVE_MODEL_PROFILES),
        "semantic_aliases": dict(SEMANTIC_TO_PRODUCT_NATIVE),
        "accepted": list(PUBLIC_MODEL_PROFILES),
        "normalization": dict(PRODUCT_NATIVE_TO_SEMANTIC),
        "max_mapped": False,
    }


def _root_subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    raise RuntimeError("PR8_14_ROOT_SUBPARSERS_MISSING")


def _configure_send_profile(parser: argparse.ArgumentParser) -> None:
    root = _root_subparsers(parser)
    send = root.choices.get("send")
    if send is None:
        raise RuntimeError("PR8_14_SEND_COMMAND_MISSING")
    for action in send._actions:
        if action.dest != "profile":
            continue
        action.type = _argparse_model_profile
        action.choices = None
        action.metavar = "{INSTANT,MEDIUM,HIGH,FAST,BALANCED,DEEP}"
        action.help = (
            "product model profile; default HIGH. Semantic aliases remain supported: "
            "FAST=INSTANT, BALANCED=MEDIUM, DEEP=HIGH"
        )
        return
    raise RuntimeError("PR8_14_SEND_PROFILE_ARGUMENT_MISSING")


def _add_inspection_common(command: argparse.ArgumentParser) -> None:
    command.add_argument("--auth-file", type=Path, default=DEFAULT_AUTH_FILE)
    command.add_argument(
        "--transport",
        choices=SUPPORTED_PRODUCT_TRANSPORTS,
        default=DEFAULT_PRODUCT_TRANSPORT,
        help="product transport to inspect; no automatic fallback is performed",
    )
    command.add_argument(
        "--json",
        action="store_true",
        help="print the stable PR8.14 machine-readable schema",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = legacy_cli._build_parser()
    parser.prog = "cwa"
    _configure_send_profile(parser)
    root = _root_subparsers(parser)

    status = root.add_parser(
        "status",
        help="inspect product-runtime readiness without performing a write",
    )
    _add_inspection_common(status)
    status.add_argument(
        "--conversation",
        help="optional raw conversation id or ChatGPT conversation URL to check canonically",
    )

    capabilities = root.add_parser(
        "capabilities",
        help="inspect evidence-backed product capabilities without performing a write",
    )
    _add_inspection_common(capabilities)

    messages = root.add_parser(
        "messages",
        help="read normalized messages from the canonical current conversation branch",
    )
    _add_inspection_common(messages)
    messages.add_argument("conversation", help="raw conversation id or ChatGPT conversation URL")
    messages.add_argument("--limit", type=int)
    messages.add_argument(
        "--role",
        action="append",
        dest="roles",
        help="include only this role; repeat to select multiple roles",
    )
    messages.add_argument(
        "--include-empty",
        action="store_true",
        help="include messages whose normalized text is empty",
    )

    return parser


def _json_print(payload: dict[str, Any], *, stream=None) -> None:
    print(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        file=stream if stream is not None else sys.stdout,
    )


def _runtime_for(args: argparse.Namespace):
    return assemble_product_runtime(
        transport=args.transport,
        auth_file=args.auth_file,
    )


def _run_status(args: argparse.Namespace) -> int:
    runtime = _runtime_for(args)
    health = runtime.health(args.conversation)
    payload = {
        "schema": CLI_CONTRACT_SCHEMA,
        "command": "status",
        "ok": bool(health.ready),
        "transport": runtime.transport,
        "health": health.to_dict(),
    }
    if args.json:
        _json_print(payload)
    else:
        print(f"ready: {str(bool(health.ready)).lower()}")
        print(f"transport: {runtime.transport}")
        print(f"reason: {health.reason}")
        if health.conversation_id is not None:
            print(f"conversation_id: {health.conversation_id}")
        if health.canonical_status is not None:
            print(f"canonical_status: {health.canonical_status}")
        if health.extension_connected is not None:
            print(f"extension_connected: {str(bool(health.extension_connected)).lower()}")
    return EXIT_OK if health.ready else EXIT_UNAVAILABLE


def _run_capabilities(args: argparse.Namespace) -> int:
    runtime = _runtime_for(args)
    capabilities = runtime.capabilities().to_dict()
    payload = {
        "schema": CLI_CONTRACT_SCHEMA,
        "command": "capabilities",
        "ok": True,
        "transport": runtime.transport,
        "product": capabilities,
        "model_profiles": model_profile_contract(),
    }
    if args.json:
        _json_print(payload)
    else:
        print(f"transport: {runtime.transport}")
        entries = capabilities.get("capabilities", {})
        for name in sorted(entries):
            entry = entries[name]
            state = entry.get("state", "UNKNOWN") if isinstance(entry, dict) else "UNKNOWN"
            owner = entry.get("owner", "UNKNOWN") if isinstance(entry, dict) else "UNKNOWN"
            print(f"{name}: {state} ({owner})")
        print("model_profiles: INSTANT MEDIUM HIGH")
        print("aliases: FAST=INSTANT BALANCED=MEDIUM DEEP=HIGH")
    return EXIT_OK


def _run_messages(args: argparse.Namespace) -> int:
    if args.limit is not None and args.limit < 0:
        raise ValueError("--limit must be greater than or equal to 0")
    runtime = _runtime_for(args)
    ref = ConversationRef.from_any(args.conversation)
    messages = runtime.get_messages(
        ref,
        limit=args.limit,
        roles=args.roles,
        include_empty=args.include_empty,
    )
    payload = {
        "schema": CLI_CONTRACT_SCHEMA,
        "command": "messages",
        "ok": True,
        "conversation_id": ref.conversation_id,
        "count": len(messages),
        "messages": [message.to_dict() for message in messages],
    }
    if args.json:
        _json_print(payload)
    else:
        for message in messages:
            role = message.role or "unknown"
            print(f"[{role}] {message.text}")
    return EXIT_OK


def _legacy_dispatch(args: argparse.Namespace) -> int:
    if args.command == "auth":
        return legacy_cli._run_auth(args)
    if args.command == "snapshot":
        return legacy_cli._run_snapshot(args)
    if args.command == "send":
        return legacy_cli._run_send(args)
    if args.command == "browser-native":
        return legacy_cli._run_browser_native(args)
    if args.command == "runtime":
        return legacy_cli._run_runtime(args)
    raise ValueError(f"unsupported command: {args.command}")


def _error_exit_code(error: BaseException) -> int:
    if getattr(error, "reconciliation_required", False) is True:
        return EXIT_RECONCILIATION_REQUIRED
    if isinstance(error, (TypeError, ValueError)):
        return EXIT_USAGE
    return EXIT_OPERATION_FAILED


def _error_payload(args: argparse.Namespace, error: BaseException, exit_code: int) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "type": type(error).__name__,
        "message": str(error),
        "exit_code": exit_code,
    }
    for name in (
        "request_stage",
        "status_code",
        "endpoint",
        "write_may_have_been_submitted",
        "reconciliation_required",
    ):
        if hasattr(error, name):
            detail[name] = getattr(error, name)
    return {
        "schema": CLI_CONTRACT_SCHEMA,
        "command": getattr(args, "command", None),
        "ok": False,
        "error": detail,
    }


def _emit_error(args: argparse.Namespace, error: BaseException, exit_code: int) -> None:
    if getattr(args, "json", False):
        _json_print(_error_payload(args, error, exit_code), stream=sys.stderr)
    else:
        print(f"error: {error}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            return _run_status(args)
        if args.command == "capabilities":
            return _run_capabilities(args)
        if args.command == "messages":
            return _run_messages(args)
        return _legacy_dispatch(args)
    except Exception as error:
        exit_code = _error_exit_code(error)
        _emit_error(args, error, exit_code)
        return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
