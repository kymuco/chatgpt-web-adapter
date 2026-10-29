"""Experimental browserless HTTP + pinned JavaScript integrity implementation.

No browser fallback. The historical strict browserless-request transport is a
separate implementation and remains unchanged.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .browserless_stream import parse_event
from .client import ChatGPTWebClient
from .exceptions import RequestError
from .sentinel_requirements import build_sentinel_prepare_headers
from .sentinel_transaction import FinalizedSentinelBundle, _validate_finalize_response
from .web_session import bootstrap_web_session, suppress_web_session_debug_trace

ASSET_URL = "https://chatgpt.com/cdn/assets/200429.3d54d9c431.js"
MODULE_HASH = "21a5313fc55570e213891f3f6daef5a596130a8a5cd12b8d90a94e37944321ed"
RUNTIME = Path(__file__).with_name("browserless_js") / "runtime.cjs"
_DEEP_RESEARCH_HINT = "plugin:connector_openai_deep_research"


def fetch_protocol_module(curl: str, destination: Path) -> None:
    """Download public code without sending credentials; require reviewed hash."""
    result = subprocess.run(
        [curl, "--fail", "--silent", "--show-error", "--max-time", "30", ASSET_URL],
        capture_output=True,
        timeout=35,
    )
    if result.returncode:
        raise RequestError("browserless public protocol download failed")
    source = result.stdout.decode("utf-8")
    start = source.find("lXE:(function")
    end = (
        re.search(r"\}\),[A-Za-z0-9_$]+:\(function", source[start:])
        if start >= 0
        else None
    )
    if end is None:
        raise RequestError("browserless protocol module boundary changed")
    module = source[start : start + end.start() + 2].encode("utf-8")
    if hashlib.sha256(module).hexdigest() != MODULE_HASH:
        raise RequestError("browserless protocol changed: unreviewed module hash")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(module)


class BrowserlessHTTPClient(ChatGPTWebClient):
    """Direct requests using saved auth, HTTP bootstrap and Node (not Chromium).

    The first send downloads a hash-pinned public protocol module when missing.
    Credentials are never passed to Node. No automatic conversation-write retry.
    Use a dedicated instance; sends on an instance are serialized.
    """

    _parse_event = staticmethod(parse_event)

    def __init__(
        self,
        *,
        auth_file: str | Path = "auth_data.json",
        protocol_module: str | Path | None = None,
        node_bin: str | None = None,
        timeout: int = 60,
    ) -> None:
        super().__init__(
            auth_file=auth_file,
            timeout=timeout,
            auto_login=False,
            auto_sentinel=False,
            auto_refresh_auth=False,
            persist_refreshed_auth=False,
        )
        self.node_bin = node_bin or shutil.which("node")
        if not self.node_bin:
            raise RequestError("browserless HTTP requires Node 24+ on PATH")
        self.protocol_module = (
            Path(protocol_module)
            if protocol_module
            else (
                Path.home()
                / ".cache"
                / "chatgpt-web-adapter"
                / MODULE_HASH
                / "integrity-module.js"
            )
        )
        self._browserless_lock = threading.RLock()
        self.last_timing: dict[str, float | None] = {}

    def _js(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.protocol_module.is_file():
            fetch_protocol_module(self.curl_bin, self.protocol_module)
        data = {
            **data,
            "modulePath": str(self.protocol_module.resolve()),
            "userAgent": self.base_headers.get("user-agent"),
            "uuid": str(uuid.uuid4()),
        }
        result = subprocess.run(
            [
                self.node_bin,
                "--permission",
                f"--allow-fs-read={RUNTIME.parent}",
                f"--allow-fs-read={self.protocol_module.resolve()}",
                str(RUNTIME),
            ],
            input=json.dumps(data),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode:
            raise RequestError(
                "browserless JS runtime failed; check Node version and protocol hash"
            )
        try:
            output = json.loads(result.stdout)
        except ValueError:
            raise RequestError("browserless JS runtime returned invalid JSON") from None
        if not isinstance(output, dict) or output.get("error"):
            raise RequestError("browserless JS computation failed")
        return output

    def _acquire_http_bundle(self, client: Any) -> FinalizedSentinelBundle:
        started = time.perf_counter()
        prepare_input = self._js({"mode": "prepare"})["prepareInput"]
        status, data = self._json_request(
            "POST",
            "https://chatgpt.com/backend-api/sentinel/chat-requirements/prepare",
            {"p": prepare_input},
            build_sentinel_prepare_headers(self),
        )
        # A successful HTTP status alone does not establish a usable Sentinel
        # prepare response. Record only bounded structural details, never tokens,
        # challenge descriptors, cookies or raw response contents.
        if status != 200:
            failure = "http_status"
        elif not isinstance(data, dict):
            failure = "non_object_response"
        else:
            token = data.get("prepare_token")
            failure = (
                "missing_prepare_token"
                if not isinstance(token, str) or not token.strip()
                else None
            )
        if failure is not None:
            raise RequestError(
                f"browserless Sentinel prepare rejected: {failure}; "
                f"http_status={status}; response_type={type(data).__name__}",
                status_code=status,
                endpoint="/backend-api/sentinel/chat-requirements/prepare",
                request_stage="sentinel_prepare",
            )
        prepared = time.perf_counter()
        solved = self._js(
            {"mode": "solve", "prepareInput": prepare_input, "requirements": data}
        )
        token, proof = solved.get("turnstileToken"), solved.get("proofToken")
        if data.get("turnstile", {}).get("required"):
            try:
                decoded = base64.b64decode(token, validate=True).decode("utf-8")
            except (ValueError, TypeError, UnicodeError):
                raise RequestError("browserless VM returned invalid evidence") from None
            if not decoded or re.match(r"^\d+: ", decoded) or token.isdigit():
                raise RequestError("browserless VM did not complete")
        if data.get("proofofwork", {}).get("required") and (
            not isinstance(proof, str) or not proof.endswith("~S")
        ):
            raise RequestError("browserless proof computation did not complete")
        computed = time.perf_counter()
        acquired, wall = time.monotonic(), time.time()
        status, final = self._json_request(
            "POST",
            "https://chatgpt.com/backend-api/sentinel/chat-requirements/finalize",
            {
                "prepare_token": data["prepare_token"],
                "proofofwork": proof,
                "turnstile": token,
            },
            self._build_headers({"origin": "https://chatgpt.com"}),
        )
        requirements, expires = _validate_finalize_response(
            status,
            final,
            acquired_monotonic=acquired,
            acquired_wallclock=wall,
        )
        self.last_timing.update(
            sentinel_prepare_seconds=prepared - started,
            js_seconds=computed - prepared,
            sentinel_finalize_seconds=time.perf_counter() - computed,
        )
        # The existing prepared-send machinery otherwise starts a refill thread.
        # This provider supplies exactly one fresh bundle per explicit send.
        client.set_sentinel_bundle_provider(None)
        return FinalizedSentinelBundle(
            requirements,
            proof or "",
            token or "",
            acquired,
            expires,
            source="browserless-http-js",
        )

    def _upload_media_files(self, media):
        import mimetypes

        from .exceptions import MediaError
        from .legacy_client_core import _detect_file_type

        uploaded = []
        for value, filename in media:
            data = self._media_to_bytes(value)
            try:
                _detect_file_type(data)
            except MediaError:
                name = filename or (
                    Path(value).name if isinstance(value, (str, Path)) else None
                )
                if not name:
                    raise ValueError("non-image bytes require an explicit filename")
                mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
                headers = self._build_headers({"content-type": "application/json"})
                status, created = self._json_request(
                    "POST",
                    "https://chatgpt.com/backend-api/files",
                    {"file_name": name, "file_size": len(data), "use_case": "my_files"},
                    headers,
                )
                if status != 200 or not isinstance(created, dict):
                    raise RequestError("file registration failed", status_code=status)
                url, file_id = created.get("upload_url"), created.get("file_id")
                if (
                    not isinstance(url, str)
                    or not url.startswith("https://")
                    or not file_id
                ):
                    raise RequestError("invalid file upload response")
                status, _, _ = self._run_curl(
                    "PUT",
                    url,
                    {
                        "content-type": mime,
                        "x-ms-blob-type": "BlockBlob",
                        "x-ms-version": "2020-04-08",
                    },
                    data,
                    persist_cookies=False,
                )
                if not 200 <= status < 300:
                    raise RequestError("file upload failed", status_code=status)
                status, _ = self._json_request(
                    "POST",
                    f"https://chatgpt.com/backend-api/files/{file_id}/uploaded",
                    {},
                    headers,
                )
                if not 200 <= status < 300:
                    raise RequestError("file finalization failed", status_code=status)
                uploaded.append(
                    {
                        "file_id": file_id,
                        "file_name": name,
                        "file_size": len(data),
                        "mime_type": mime,
                    }
                )
            else:
                uploaded.extend(super()._upload_media_files([(data, filename)]))
        return uploaded

    @staticmethod
    def _create_messages(prompt, system, *, image_requests=None, system_hints=None):
        images = [
            f
            for f in image_requests or []
            if f.get("mime_type", "").startswith("image/")
        ]
        files = [
            f
            for f in image_requests or []
            if not f.get("mime_type", "").startswith("image/")
        ]
        messages = ChatGPTWebClient._create_messages(
            prompt, system, image_requests=images, system_hints=system_hints
        )
        if files:
            metadata = messages[-1].setdefault("metadata", {})
            metadata.setdefault("attachments", []).extend(
                {
                    "id": f["file_id"],
                    "name": f["file_name"],
                    "mimeType": f["mime_type"],
                    "size": f["file_size"],
                }
                for f in files
            )
        return messages

    def _get_ready_requirements(self):
        requirements = super()._get_ready_requirements()
        # Cached bundles bypass the provider; disable refill in that case too.
        self.set_sentinel_bundle_provider(None)
        return requirements

    def prepare_next_turn(self) -> float:
        """Prepare one expiring, single-use bundle before the prompt is ready.

        Returns preparation wall time. This shifts work before send(), not a
        reduction in total work. Expired bundles are reacquired by send().
        """
        from .sentinel_bundle import prefetch_finalized_sentinel_bundle

        with self._browserless_lock:
            if getattr(self, "_browserless_sending", False):
                raise RuntimeError("cannot prefetch during send callbacks")
            started = time.perf_counter()
            with suppress_web_session_debug_trace():
                if not bootstrap_web_session(self):
                    raise RequestError(
                        "HTTP bootstrap did not establish device context"
                    )
                self.set_sentinel_bundle_provider(self._acquire_http_bundle)
                try:
                    prefetch_finalized_sentinel_bundle(self)
                finally:
                    self.set_sentinel_bundle_provider(None)
            return time.perf_counter() - started

    def send(
        self,
        prompt: str,
        *,
        model: str = "gpt-6-instant",
        temporary: bool = False,
        conversation: Any = None,
        on_token: Any = None,
        on_event: Any = None,
        reasoning_effort: str | None = None,
        conversation_origin: str | None = None,
        media: Any = None,
        deep_research: bool = False,
    ):
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be nonempty")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a nonempty web model slug")
        if conversation_origin is not None and conversation_origin not in {
            "flora",
            "tpp",
        }:
            raise ValueError("conversation_origin must be flora or tpp")
        if deep_research:
            if temporary or conversation is not None or media is not None:
                raise ValueError(
                    "deep_research currently requires a new, non-temporary text chat"
                )
            if conversation_origin is not None:
                raise ValueError("deep_research cannot set conversation_origin")
        with self._browserless_lock:
            if getattr(self, "_browserless_sending", False):
                raise RuntimeError(
                    "reentrant send on the same browserless client is not supported"
                )
            start = time.perf_counter()
            self.last_timing = {"ttft_seconds": None, "stream_ttft_seconds": None}
            if not bootstrap_web_session(self):
                raise RequestError("HTTP bootstrap did not establish device context")
            self.last_timing["bootstrap_seconds"] = time.perf_counter() - start
            if isinstance(conversation, str):
                conversation = self.attach_conversation(conversation).conversation
            stream_start = None

            def token_callback(text):
                if text and self.last_timing["ttft_seconds"] is None:
                    now = time.perf_counter()
                    self.last_timing["ttft_seconds"] = now - start
                    self.last_timing["stream_ttft_seconds"] = (
                        now - stream_start if stream_start else None
                    )
                if on_token:
                    on_token(text)

            def event_callback(event):
                nonlocal stream_start
                if event.get("type") == "stream_started":
                    stream_start = time.perf_counter()
                if on_event:
                    on_event(event)

            self.set_sentinel_bundle_provider(self._acquire_http_bundle)
            self._browserless_sending = True
            try:
                with suppress_web_session_debug_trace():
                    return super().send(
                        prompt,
                        model=model,
                        temporary=temporary,
                        conversation=conversation,
                        reasoning_effort=reasoning_effort,
                        on_token=token_callback,
                        on_event=event_callback,
                        media=media,
                        **(
                            {"_system_hints": [_DEEP_RESEARCH_HINT]}
                            if deep_research
                            else {}
                        ),
                        **(
                            {"conversation_origin": conversation_origin}
                            if conversation_origin
                            else {}
                        ),
                    )
            finally:
                self._browserless_sending = False
                self.set_sentinel_bundle_provider(None)
                self.last_timing["total_seconds"] = time.perf_counter() - start
