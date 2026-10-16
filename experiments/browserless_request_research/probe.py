"""Opt-in JS-only protocol experiment. No proven inference support yet."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.sentinel_requirements import build_sentinel_prepare_headers
from chatgpt_web_adapter.sentinel_transaction import (
    FinalizedSentinelBundle,
    _validate_finalize_response,
)
from chatgpt_web_adapter.web_session import bootstrap_web_session

ROOT = Path(__file__).resolve().parent
MODULE = ROOT / "cache" / "integrity-module.js"
ASSET_URL = "https://chatgpt.com/cdn/assets/200429.3d54d9c431.js"
MODULE_HASH = "21a5313fc55570e213891f3f6daef5a596130a8a5cd12b8d90a94e37944321ed"


def fetch_module(curl: str) -> None:
    response = subprocess.run(
        [curl, "--fail", "--silent", "--show-error", "--max-time", "30", ASSET_URL],
        capture_output=True,
        timeout=35,
    )
    if response.returncode:
        raise RuntimeError("public asset download failed")
    source = response.stdout.decode("utf-8")
    start = source.index("lXE:(function")
    end = re.search(r"\}\),[A-Za-z0-9_$]+:\(function", source[start:])
    if end is None:
        raise RuntimeError("module boundary changed")
    module = source[start : start + end.start() + 2].encode()
    if hashlib.sha256(module).hexdigest() != MODULE_HASH:
        raise RuntimeError("unreviewed integrity module hash")
    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_bytes(module)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--fetch-module", action="store_true")
    parser.add_argument(
        "--send", action="store_true", help="Attempt at most one conversation write"
    )
    parser.add_argument("--mode", choices=("temporary", "normal"), default="temporary")
    parser.add_argument(
        "--model",
        default="gpt-6-instant",
        help="Exact catalogue slug; no alias guessing",
    )
    parser.add_argument("--conversation", help="Existing persistent conversation ID")
    parser.add_argument("--prompt", default="Reply with exactly: CWA_BROWSERLESS_OK")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.conversation and args.mode == "temporary":
        parser.error("continuation requires --mode normal")
    report = {
        "schema": 1,
        "browser_started": False,
        "experimental": True,
        "requested_model": args.model,
        "requested_mode": args.mode,
        "write_attempted": False,
        "inference_verified": False,
        "temporary_semantics_verified": False,
        "ttft_seconds": None,
    }
    stage = "setup"
    start = time.perf_counter()
    try:
        node = shutil.which("node")
        curl = shutil.which("curl.exe") or shutil.which("curl")
        if not node or not curl:
            raise RuntimeError("Node 24+ and curl are required")
        if args.fetch_module:
            fetch_module(curl)
        if not MODULE.is_file():
            raise RuntimeError("run with --fetch-module once")
        client = ChatGPTWebClient(
            auth_file=args.auth_file,
            auto_login=False,
            auto_sentinel=False,
            auto_refresh_auth=False,
            persist_refreshed_auth=False,
            timeout=45,
        )
        stage = "http_session_bootstrap"
        report["device_context_ready"] = bootstrap_web_session(client)

        def js(data):
            data.update(
                userAgent=client.base_headers.get("user-agent"),
                uuid=str(uuid.uuid4()),
                modulePath=str(MODULE),
            )
            result = subprocess.run(
                [
                    node,
                    "--permission",
                    f"--allow-fs-read={ROOT}",
                    str(ROOT / "runtime.cjs"),
                ],
                input=json.dumps(data),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode:
                raise RuntimeError("JS subprocess failed (details withheld)")
            return json.loads(result.stdout)

        stage = "sentinel_prepare"
        prepare_input = js({"mode": "prepare"})["prepareInput"]
        before = time.perf_counter()
        status, data = client._json_request(
            "POST",
            "https://chatgpt.com/backend-api/sentinel/chat-requirements/prepare",
            {"p": prepare_input},
            build_sentinel_prepare_headers(client),
        )
        report["prepare_status"] = status
        report["prepare_seconds"] = time.perf_counter() - before
        if status != 200 or not isinstance(data, dict):
            raise RuntimeError("prepare rejected")
        stage = "js_vm"
        before = time.perf_counter()
        solved = js(
            {"mode": "solve", "prepareInput": prepare_input, "requirements": data}
        )
        report["js_seconds"] = time.perf_counter() - before
        vm_failed = bool(solved.get("error"))
        token = solved.get("turnstileToken")
        if data.get("turnstile", {}).get("required"):
            if not isinstance(token, str) or not token:
                vm_failed = True
            else:
                try:
                    decoded = base64.b64decode(token, validate=True).decode("utf-8")
                    vm_failed |= bool(re.match(r"^\d+: ", decoded)) or token.isdigit()
                except (ValueError, UnicodeError):
                    vm_failed = True
        proof = solved.get("proofToken")
        if data.get("proofofwork", {}).get("required"):
            vm_failed |= not isinstance(proof, str) or not proof.endswith("~S")
        report["vm_completed_without_known_error"] = not vm_failed
        if vm_failed:
            raise RuntimeError(
                "VM or proof computation failed; no finalize or write attempted"
            )
        if not args.send:
            report["outcome"] = "PREPARE_ONLY_NOT_INFERENCE"
        else:
            stage = "sentinel_finalize"
            acquired, wall = time.monotonic(), time.time()
            status, final = client._json_request(
                "POST",
                "https://chatgpt.com/backend-api/sentinel/chat-requirements/finalize",
                {
                    "prepare_token": data["prepare_token"],
                    "proofofwork": proof,
                    "turnstile": token,
                },
                client._build_headers({"origin": "https://chatgpt.com"}),
            )
            report["finalize_status"] = status
            requirements, expires = _validate_finalize_response(
                status,
                final,
                acquired_monotonic=acquired,
                acquired_wallclock=wall,
            )
            bundle = FinalizedSentinelBundle(
                requirements,
                proof or "",
                token or "",
                acquired,
                expires,
                source="browserless-js-research",
            )
            used = False

            def provider(c):
                nonlocal used
                if used:
                    raise RuntimeError("one-shot bundle already used")
                used = True
                c.set_sentinel_bundle_provider(None)  # No automatic background refill.
                return bundle

            client.set_sentinel_bundle_provider(provider)
            conversation = None
            if args.conversation:
                stage = "canonical_attach"
                conversation = client.attach_conversation(
                    args.conversation
                ).conversation

            def on_token(text):
                if text and report["ttft_seconds"] is None:
                    report["ttft_seconds"] = time.perf_counter() - start

            def on_event(event):
                kind = event.get("type")
                if kind == "raw_sse_event":
                    parsed = event.get("parsed")
                    if isinstance(parsed, dict):
                        summary = {
                            "t": round(time.perf_counter() - start, 4),
                            "keys": list(parsed),
                            "type": parsed.get("type"),
                            "p": parsed.get("p"),
                            "o": parsed.get("o"),
                        }
                        value = parsed.get("v")
                        if isinstance(value, dict):
                            summary["value_keys"] = list(value)
                            message = value.get("message")
                            if isinstance(message, dict):
                                summary["message_role"] = message.get("author", {}).get(
                                    "role"
                                )
                                summary["content_type"] = message.get(
                                    "content", {}
                                ).get("content_type")
                                summary["text_lengths"] = [
                                    len(p)
                                    for p in message.get("content", {}).get("parts", [])
                                    if isinstance(p, str)
                                ]
                        elif isinstance(value, list):
                            summary["patches"] = [
                                {
                                    "p": p.get("p"),
                                    "o": p.get("o"),
                                    "v_type": type(p.get("v")).__name__,
                                }
                                for p in value
                                if isinstance(p, dict)
                            ]
                        report.setdefault("sse_structure", []).append(summary)
                if event.get("type") == "stream_started":
                    report["write_attempted"] = True
                    report["stream_start_seconds"] = time.perf_counter() - start

            stage = "conversation_send"
            response = client.send(
                args.prompt,
                model=args.model,
                temporary=args.mode == "temporary",
                reasoning_effort=None,
                conversation=conversation,
                on_token=on_token,
                on_event=on_event,
            )
            report.update(
                outcome="STREAM_RETURNED_UNVERIFIED",
                response_characters=len(response.text),
                observed_model=response.request.observed_model
                if response.request
                else None,
                conversation_id=response.conversation.conversation_id,
                message_id=response.conversation.message_id,
                expected_text_matches=response.text.strip() == "CWA_BROWSERLESS_OK",
            )
            stage = "canonical_verification"
            try:
                snapshot = client._get_conversation_payload(
                    response.conversation.conversation_id
                )
                report["conversation_flags"] = {
                    key: snapshot.get(key)
                    for key in (
                        "is_temporary_chat",
                        "history_and_training_disabled",
                        "is_archived",
                    )
                }
                messages = client.get_messages(response.conversation.conversation_id)
                matching = [
                    m
                    for m in messages
                    if m.message_id == response.conversation.message_id
                    and m.role == "assistant"
                ]
                report["canonical_text_matches"] = bool(
                    matching and matching[-1].text == response.text
                )
                report["canonical_model"] = matching[-1].model if matching else None
                report["inference_verified"] = report["canonical_text_matches"]
            except Exception as error:
                report["canonical_read_status"] = getattr(error, "status_code", None)
            # This lab intentionally never equates a stream with canonical finality,
            # persistence or a verified Temporary Chat. Those require a next gate.
    except Exception as error:
        report.update(
            outcome="FAILED",
            stage=stage,
            error_type=type(error).__name__,
            status_code=getattr(error, "status_code", None),
        )
    report["elapsed_seconds"] = time.perf_counter() - start
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report.get("outcome") == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
