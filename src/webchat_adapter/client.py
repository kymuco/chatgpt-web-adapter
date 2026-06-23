from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import urlparse

from .auth import CHAT_URL, DEFAULT_AUTH_FILE, build_base_headers, load_auth_data
from .exceptions import MediaError, RequestError
from .types import AuthData, ChatConversation, ChatMetrics, ChatResponse, MediaItem

CHAT_REQUIREMENTS_URL = "https://chatgpt.com/backend-api/sentinel/chat-requirements"
CHAT_BACKEND_URL = "https://chatgpt.com/backend-api/f/conversation"
CHAT_CONVERSATION_PREPARE_URL = "https://chatgpt.com/backend-api/f/conversation/prepare"
CHAT_CONVERSATION_URL = "https://chatgpt.com/backend-api/conversation/{conversation_id}"
CHAT_CONVERSATIONS_URL = "https://chatgpt.com/backend-api/conversations"
CHAT_FILES_URL = "https://chatgpt.com/backend-api/files"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT_SECONDS = 90
PREFETCH_TTL_SECONDS = 20.0
DEFAULT_APPROVAL_POLL_TIMEOUT_SECONDS = 90.0
DEFAULT_APPROVAL_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_PENDING_POLL_INTERVAL_SECONDS = 3.0
DEFAULT_APPROVAL_SETTLE_DELAY_SECONDS = 2.0
TRACE_REDACTED = "<redacted>"
TRACE_HEADER_REDACT_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "openai-sentinel-chat-requirements-token",
    "openai-sentinel-proof-token",
    "openai-sentinel-turnstile-token",
}
MODEL_ALIASES = {
    "gpt-5.1": "gpt-5-1",
    "gpt-4.1": "gpt-4.1",
    "gpt-4.1-mini": "gpt-4.1-mini",
    "gpt-4.5": "gpt-4.5",
}
UPLOAD_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.8",
    "priority": "u=1, i",
    "referer": CHAT_URL,
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
}


def _generate_answer(
    seed: str,
    diff: str,
    config: list[Any],
    max_attempts: int = 500_000,
) -> tuple[str, bool]:
    seed_encoded = seed.encode()
    p1 = (json.dumps(config[:3], separators=(",", ":"), ensure_ascii=False)[:-1] + ",").encode()
    p2 = ("," + json.dumps(config[4:9], separators=(",", ":"), ensure_ascii=False)[1:-1] + ",").encode()
    p3 = ("," + json.dumps(config[10:], separators=(",", ":"), ensure_ascii=False)[1:]).encode()
    target_diff = bytes.fromhex(diff)
    diff_len = len(target_diff)
    for i in range(max_attempts):
        d1 = str(i).encode()
        d2 = str(i >> 1).encode()
        string = p1 + d1 + p2 + d2 + p3
        encoded = base64.b64encode(string)
        hash_value = hashlib.new("sha3_512", seed_encoded + encoded).digest()
        if hash_value[:diff_len] <= target_diff:
            return encoded.decode(), True
    fallback = base64.b64encode(f'"{seed}"'.encode()).decode()
    return "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D" + fallback, False


def _get_requirements_token(config: list[Any]) -> str:
    answer, solved = _generate_answer(format(random.random()), "0fffff", config)
    if not solved:
        raise RequestError("Failed to solve requirements challenge")
    return "gAAAAAC" + answer


def _generate_proof_token(
    *,
    required: bool,
    seed: str = "",
    difficulty: str = "",
    user_agent: str | None = None,
    proof_token: Any = None,
) -> str | None:
    if not required:
        return None
    if proof_token is None:
        screen = random.choice([3008, 4010, 6000]) * random.choice([1, 2, 4])
        parse_time = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        proof_token = [
            screen,
            parse_time,
            None,
            0,
            user_agent,
            "https://tcr9i.chat.openai.com/v2/35536E1E-65B4-4D96-9D97-6ADB7EFF8147/api.js",
            "dpl=1440a687921de39ff5ee56b92807faaadce73f13",
            "en",
            "en-US",
            None,
            "plugins-[object PluginArray]",
            random.choice(
                [
                    "_reactListeningcfilawjnerp",
                    "_reactListening9ne2dfo1i47",
                    "_reactListening410nzwhan2a",
                ]
            ),
            random.choice(["alert", "ontransitionend", "onprogress"]),
        ]
    diff_len = len(difficulty)
    for i in range(100_000):
        proof_token[3] = i
        payload = json.dumps(proof_token)
        encoded = base64.b64encode(payload.encode()).decode()
        hash_value = hashlib.sha3_512((seed + encoded).encode()).digest()
        if hash_value.hex()[:diff_len] <= difficulty:
            return "gAAAAAB" + encoded
    fallback = base64.b64encode(f'"{seed}"'.encode()).decode()
    return "gAAAAABwQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D" + fallback


def _extract_data_uri(data_uri: str) -> bytes:
    match = re.match(r"^data:([^;]+);base64,(.+)$", data_uri, re.IGNORECASE | re.DOTALL)
    if not match:
        raise MediaError("Invalid data URI")
    try:
        return base64.b64decode(match.group(2))
    except Exception as error:
        raise MediaError(f"Invalid base64 data URI: {error}") from error


def _detect_file_type(binary_data: bytes) -> tuple[str, str]:
    if binary_data.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if binary_data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if binary_data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif", "image/gif"
    if binary_data.startswith(b"RIFF") and binary_data[8:12] == b"WEBP":
        return ".webp", "image/webp"
    raise MediaError("Unsupported media format")


def _get_png_size(data: bytes) -> tuple[int | None, int | None]:
    if len(data) < 24:
        return None, None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def _get_gif_size(data: bytes) -> tuple[int | None, int | None]:
    if len(data) < 10:
        return None, None
    return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")


def _get_jpeg_size(data: bytes) -> tuple[int | None, int | None]:
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if marker in {0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        segment_length = int.from_bytes(data[index:index + 2], "big")
        if segment_length < 2 or index + segment_length > len(data):
            break
        if marker in {
            0xC0, 0xC1, 0xC2, 0xC3,
            0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB,
            0xCD, 0xCE, 0xCF,
        }:
            if index + 7 <= len(data):
                height = int.from_bytes(data[index + 3:index + 5], "big")
                width = int.from_bytes(data[index + 5:index + 7], "big")
                return width, height
            break
        index += segment_length
    return None, None


def _get_webp_size(data: bytes) -> tuple[int | None, int | None]:
    if len(data) < 30:
        return None, None
    chunk_type = data[12:16]
    if chunk_type == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk_type == b"VP8 " and len(data) >= 30:
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    if chunk_type == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    return None, None


def _get_image_size(data: bytes, mime_type: str) -> tuple[int | None, int | None]:
    if mime_type == "image/png":
        return _get_png_size(data)
    if mime_type == "image/gif":
        return _get_gif_size(data)
    if mime_type == "image/jpeg":
        return _get_jpeg_size(data)
    if mime_type == "image/webp":
        return _get_webp_size(data)
    return None, None


class ChatGPTWebClient:
    """Minimal sync adapter for chatgpt.com web sessions."""

    def __init__(
        self,
        auth: AuthData | None = None,
        *,
        auth_file: str | Path = DEFAULT_AUTH_FILE,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        curl_bin: str | None = None,
        debug_trace_dir: str | Path | None = None,
        debug_trace_sanitize: bool = True,
    ) -> None:
        self.auth = auth or load_auth_data(auth_file)
        self.timeout = max(10, int(timeout))
        self.base_headers = build_base_headers(self.auth)
        self.curl_bin = curl_bin or shutil.which("curl.exe") or shutil.which("curl")
        if not self.curl_bin:
            raise RequestError(
                "curl executable was not found. Install curl or run on a system where curl is available."
            )
        self.prefetched_requirements: dict[str, Any] | None = None
        self.prefetched_proof_header: str | None = None
        self.prefetched_ts = 0.0
        self._file_cache: dict[str, dict[str, Any]] = {}
        self.debug_trace_dir = Path(debug_trace_dir) if debug_trace_dir is not None else None
        self.debug_trace_sanitize = bool(debug_trace_sanitize)
        self._debug_trace_counter = 0

    def _build_headers(self, extra: dict[str, str | None] | None = None) -> dict[str, str]:
        headers = dict(self.base_headers)
        if self.auth.accessToken:
            headers["authorization"] = f"Bearer {self.auth.accessToken}"
        if self.auth.cookies:
            headers["cookie"] = "; ".join(f"{key}={value}" for key, value in self.auth.cookies.items())
        if extra:
            headers.update({key: value for key, value in extra.items() if value is not None})
        return headers

    @staticmethod
    def _emit_event(
        callback: Callable[[dict[str, Any]], None] | None,
        event_type: str,
        **payload: Any,
    ) -> None:
        if callback is None:
            return
        callback({"type": event_type, **payload})

    @staticmethod
    def _read_media_path(path_like: str | Path | os.PathLike[str]) -> bytes:
        path = Path(path_like)
        try:
            return path.read_bytes()
        except OSError as error:
            raise MediaError(f"Failed to read media file {path}: {error}") from error

    @staticmethod
    def _cleanup_process(process: subprocess.Popen | None, *, timeout: float = 1.0) -> None:
        if process is None:
            return
        try:
            running = process.poll() is None
        except Exception:
            running = False
        if running:
            try:
                process.terminate()
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=timeout)
            except OSError:
                pass
        for stream_name in ("stdout", "stderr"):
            stream = getattr(process, stream_name, None)
            if stream is None:
                continue
            try:
                stream.close()
            except OSError:
                pass

    def _update_cookies_from_text(self, header_text: str) -> None:
        for raw_line in header_text.splitlines():
            if not raw_line.lower().startswith("set-cookie:"):
                continue
            raw_cookie = raw_line.split(":", 1)[1].strip()
            jar = SimpleCookie()
            jar.load(raw_cookie)
            for key, morsel in jar.items():
                self.auth.cookies[key] = morsel.value

    @staticmethod
    def _extract_status_code(header_text: str) -> int:
        status = 0
        for raw_line in header_text.splitlines():
            line = raw_line.strip()
            if not line.startswith("HTTP/"):
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                status = int(parts[1])
        return status

    def _debug_trace_enabled(self) -> bool:
        return isinstance(getattr(self, "debug_trace_dir", None), Path)

    def _next_debug_trace_path(self, kind: str) -> Path:
        trace_dir = getattr(self, "debug_trace_dir", None)
        if not isinstance(trace_dir, Path):
            raise RuntimeError("debug trace directory is not configured")
        trace_dir.mkdir(parents=True, exist_ok=True)
        counter = int(getattr(self, "_debug_trace_counter", 0)) + 1
        self._debug_trace_counter = counter
        return trace_dir / f"{counter:04d}-{kind}.json"

    def _sanitize_header_value(self, key: str, value: str) -> str:
        if not bool(getattr(self, "debug_trace_sanitize", True)):
            return value
        if key.strip().lower() in TRACE_HEADER_REDACT_KEYS:
            return TRACE_REDACTED
        return value

    def _sanitize_headers_mapping(self, headers: dict[str, str]) -> dict[str, str]:
        return {
            key: self._sanitize_header_value(key, value)
            for key, value in headers.items()
        }

    def _sanitize_header_lines(self, header_text: str) -> list[str]:
        lines: list[str] = []
        for raw_line in header_text.splitlines():
            if ":" not in raw_line:
                if raw_line.strip():
                    lines.append(raw_line)
                continue
            key, value = raw_line.split(":", 1)
            lines.append(f"{key}: {self._sanitize_header_value(key, value.strip())}")
        return lines

    @staticmethod
    def _trace_text_repr(text: str, *, max_chars: int = 200_000) -> dict[str, Any]:
        truncated = len(text) > max_chars
        return {
            "kind": "text",
            "size": len(text),
            "truncated": truncated,
            "text": text[:max_chars],
        }

    def _trace_bytes_repr(self, body: bytes | None, *, max_chars: int = 200_000) -> dict[str, Any] | None:
        if body is None:
            return None
        try:
            return self._trace_text_repr(body.decode("utf-8"), max_chars=max_chars)
        except UnicodeDecodeError:
            encoded = base64.b64encode(body).decode("ascii")
            truncated = len(encoded) > max_chars
            return {
                "kind": "base64",
                "size": len(body),
                "truncated": truncated,
                "base64": encoded[:max_chars],
            }

    def _write_debug_trace(self, kind: str, payload: dict[str, Any]) -> None:
        if not self._debug_trace_enabled():
            return
        trace_path = self._next_debug_trace_path(kind)
        trace_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _build_curl_command(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        header_path: str,
        body_path: str | None = None,
        *,
        no_buffer: bool = False,
        follow_redirects: bool = False,
    ) -> list[str]:
        command = [
            self.curl_bin,
            "-sS",
            "--compressed",
            "--connect-timeout",
            "10",
            "--max-time",
            str(self.timeout),
            "-X",
            method.upper(),
            url,
            "-D",
            header_path,
        ]
        if no_buffer:
            command.insert(1, "-N")
        if follow_redirects:
            command.insert(1, "-L")
        for key, value in headers.items():
            command.extend(["-H", f"{key}: {value}"])
        if body_path is not None:
            command.extend(["--data-binary", f"@{body_path}"])
        return command

    def _run_curl(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
        *,
        persist_cookies: bool = True,
        follow_redirects: bool = False,
    ) -> tuple[int, bytes, str]:
        payload_path: str | None = None
        status = 0
        raw_body = b""
        header_text = ""
        stderr_text = ""
        error_text: str | None = None
        return_code = 0
        with tempfile.NamedTemporaryFile(delete=False) as header_file:
            header_path = header_file.name
        try:
            if body is not None:
                with tempfile.NamedTemporaryFile(delete=False) as payload_file:
                    payload_file.write(body)
                    payload_path = payload_file.name
            command = self._build_curl_command(
                method,
                url,
                headers,
                header_path,
                payload_path,
                follow_redirects=follow_redirects,
            )
            result = subprocess.run(command, capture_output=True)
            raw_body = result.stdout
            return_code = result.returncode
            stderr_text = result.stderr.decode("utf-8", errors="replace")
            header_text = Path(header_path).read_text(encoding="utf-8", errors="replace")
            if persist_cookies:
                self._update_cookies_from_text(header_text)
            status = self._extract_status_code(header_text)
            if return_code != 0 and not status:
                error_text = f"curl failed: {stderr_text.strip() or return_code}"
                raise RequestError(error_text)
            return status, raw_body, header_text
        finally:
            self._write_debug_trace(
                "http",
                {
                    "method": method.upper(),
                    "url": url,
                    "persist_cookies": bool(persist_cookies),
                    "follow_redirects": bool(follow_redirects),
                    "request_headers": self._sanitize_headers_mapping(headers),
                    "request_body": self._trace_bytes_repr(body),
                    "response_status": status,
                    "response_headers": self._sanitize_header_lines(header_text),
                    "response_body": self._trace_bytes_repr(raw_body),
                    "stderr": stderr_text or None,
                    "return_code": return_code,
                    "error": error_text,
                },
            )
            try:
                Path(header_path).unlink(missing_ok=True)
            except OSError:
                pass
            if payload_path:
                try:
                    Path(payload_path).unlink(missing_ok=True)
                except OSError:
                    pass

    def _json_request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> tuple[int, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        status, raw_body, _ = self._run_curl(method, url, headers, body)
        if not raw_body:
            return status, None
        body_text = raw_body.decode("utf-8", errors="replace")
        try:
            return status, json.loads(body_text)
        except ValueError:
            return status, body_text

    def warmup(self) -> bool:
        try:
            requirements = self._get_chat_requirements()
            proof_header = self._build_proof_header(requirements)
        except RequestError:
            return False
        token = requirements.get("token") if isinstance(requirements, dict) else None
        if isinstance(token, str) and token:
            self.prefetched_requirements = requirements
            self.prefetched_proof_header = proof_header
            self.prefetched_ts = time.monotonic()
            return True
        return False

    def _take_prefetched_requirements(self) -> tuple[dict[str, Any], str | None] | None:
        if self.prefetched_requirements is None:
            return None
        if time.monotonic() - self.prefetched_ts > PREFETCH_TTL_SECONDS:
            self.prefetched_requirements = None
            self.prefetched_proof_header = None
            self.prefetched_ts = 0.0
            return None
        requirements = self.prefetched_requirements
        proof_header = self.prefetched_proof_header
        self.prefetched_requirements = None
        self.prefetched_proof_header = None
        self.prefetched_ts = 0.0
        return requirements, proof_header

    def _get_ready_requirements(self) -> tuple[dict[str, Any], str | None]:
        prefetched = self._take_prefetched_requirements()
        if prefetched is not None:
            return prefetched
        requirements = self._get_chat_requirements()
        return requirements, self._build_proof_header(requirements)

    def _get_chat_requirements(self) -> dict[str, Any]:
        req_input = None
        if isinstance(self.auth.proof_token, list):
            try:
                req_input = _get_requirements_token(self.auth.proof_token)
            except Exception:
                req_input = None
        headers = self._build_headers({"accept": "*/*", "content-type": "application/json"})
        status, data = self._json_request("POST", CHAT_REQUIREMENTS_URL, {"p": req_input}, headers)
        if status in {401, 403}:
            raise RequestError(f"chat-requirements request rejected: status={status}")
        if status >= 400:
            raise RequestError(f"chat-requirements request failed: status={status}: {data}")
        if not isinstance(data, dict):
            raise RequestError("chat-requirements response expected JSON object")
        return data

    def _build_proof_header(self, requirements: dict[str, Any]) -> str | None:
        proof_block = requirements.get("proofofwork")
        if not isinstance(proof_block, dict):
            return None
        return _generate_proof_token(
            required=bool(proof_block.get("required")),
            seed=str(proof_block.get("seed") or ""),
            difficulty=str(proof_block.get("difficulty") or ""),
            user_agent=self.base_headers.get("user-agent"),
            proof_token=self.auth.proof_token if isinstance(self.auth.proof_token, list) else None,
        )

    def _media_to_bytes(self, media_data: Any) -> bytes:
        if isinstance(media_data, bytes):
            return media_data
        if isinstance(media_data, bytearray):
            return bytes(media_data)
        if isinstance(media_data, Path):
            return self._read_media_path(media_data)
        if isinstance(media_data, os.PathLike):
            return self._read_media_path(media_data)
        if isinstance(media_data, str):
            if media_data.startswith("data:"):
                return _extract_data_uri(media_data)
            if media_data.startswith(("http://", "https://")):
                status, raw_body, _ = self._run_curl(
                    "GET",
                    media_data,
                    {"user-agent": self.base_headers.get("user-agent", "")},
                    persist_cookies=False,
                    follow_redirects=True,
                )
                if not 200 <= status < 300:
                    raise MediaError(f"Media download failed: status={status}")
                return raw_body
            return self._read_media_path(media_data)
        raise MediaError("Unsupported media type")

    @staticmethod
    def _normalize_media_items(media: Sequence[MediaItem] | None) -> list[tuple[Any, str | None]]:
        if not media:
            return []
        items: list[tuple[Any, str | None]] = []
        for item in media:
            if isinstance(item, tuple) and len(item) == 2:
                items.append((item[0], item[1]))
            else:
                items.append((item, None))
        return items

    def _upload_media_files(self, media: Sequence[tuple[Any, str | None]]) -> list[dict[str, Any]]:
        uploaded: list[dict[str, Any]] = []
        for media_data, filename in media:
            data_bytes = self._media_to_bytes(media_data)
            cache_key = hashlib.md5(data_bytes).hexdigest()
            cached = self._file_cache.get(cache_key)
            if cached is not None:
                uploaded.append(cached.copy())
                continue
            extension, mime_type = _detect_file_type(data_bytes)
            width, height = _get_image_size(data_bytes, mime_type)
            if not filename and isinstance(media_data, (str, Path, os.PathLike)):
                parsed_path = str(media_data)
                if parsed_path.startswith(("http://", "https://")):
                    filename = Path(urlparse(parsed_path).path).name or None
                else:
                    filename = Path(parsed_path).name or None
            if not filename:
                filename = f"file-{len(data_bytes)}{extension}"
            create_headers = self._build_headers({"content-type": "application/json"})
            create_payload = {
                "file_name": filename,
                "file_size": len(data_bytes),
                "use_case": "multimodal",
            }
            status, created = self._json_request("POST", CHAT_FILES_URL, create_payload, create_headers)
            if status >= 400 or not isinstance(created, dict):
                raise RequestError(f"file create failed: status={status} body={created}")
            upload_url = created.get("upload_url")
            file_id = created.get("file_id")
            if not isinstance(upload_url, str) or not upload_url:
                raise RequestError(f"file create response missing upload_url: {created}")
            if not isinstance(file_id, str) or not file_id:
                raise RequestError(f"file create response missing file_id: {created}")
            upload_headers = {
                **UPLOAD_HEADERS,
                "content-type": mime_type,
                "origin": CHAT_URL.rstrip("/"),
                "user-agent": self.base_headers.get("user-agent", ""),
                "x-ms-blob-type": "BlockBlob",
                "x-ms-version": "2020-04-08",
            }
            upload_status, upload_body, _ = self._run_curl(
                "PUT",
                upload_url,
                upload_headers,
                data_bytes,
                persist_cookies=False,
            )
            if upload_status >= 400:
                body_text = upload_body.decode("utf-8", errors="replace")
                raise RequestError(
                    f"file upload failed: status={upload_status} body={body_text[:300]}"
                )
            finalize_status, finalized = self._json_request(
                "POST",
                f"{CHAT_FILES_URL}/{file_id}/uploaded",
                {},
                create_headers,
            )
            if finalize_status >= 400:
                raise RequestError(
                    f"file finalize failed: status={finalize_status} body={finalized}"
                )
            payload = {
                **create_payload,
                **created,
                "mime_type": mime_type,
                "extension": extension,
                "width": width,
                "height": height,
                "download_url": finalized.get("download_url") if isinstance(finalized, dict) else None,
            }
            self._file_cache[cache_key] = payload.copy()
            uploaded.append(payload)
        return uploaded

    @staticmethod
    def _create_messages(
        prompt: str,
        system: str | None,
        *,
        image_requests: list[dict[str, Any]] | None = None,
        system_hints: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if isinstance(system, str) and system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": prompt})
        payload: list[dict[str, Any]] = []
        for message in messages:
            payload.append(
                {
                    "id": str(uuid.uuid4()),
                    "author": {"role": message["role"]},
                    "content": {"content_type": "text", "parts": [str(message["content"])]},
                    "metadata": {
                        "serialization_metadata": {"custom_symbol_offsets": []},
                        **({"system_hints": system_hints} if system_hints else {}),
                    },
                    "create_time": time.time(),
                }
            )
        if image_requests:
            payload[-1]["content"] = {
                "content_type": "multimodal_text",
                "parts": [
                    *[
                        {
                            "asset_pointer": f"file-service://{image_request['file_id']}",
                            "height": image_request.get("height"),
                            "size_bytes": image_request.get("file_size"),
                            "width": image_request.get("width"),
                        }
                        for image_request in image_requests
                    ],
                    payload[-1]["content"]["parts"][0],
                ],
            }
            payload[-1]["metadata"] = {
                "attachments": [
                    {
                        "id": image_request["file_id"],
                        "mimeType": image_request.get("mime_type"),
                        "name": image_request.get("file_name"),
                        "size": image_request.get("file_size"),
                        **(
                            {
                                "height": image_request.get("height"),
                                "width": image_request.get("width"),
                            }
                            if image_request.get("width") and image_request.get("height")
                            else {}
                        ),
                    }
                    for image_request in image_requests
                ]
            }
        return payload

    @staticmethod
    def _parse_event(payload: Any, state: dict[str, Any]) -> tuple[list[str], str | None]:
        if not isinstance(payload, dict):
            return [], None
        if payload.get("error"):
            raise RequestError(str(payload.get("error")))
        if payload.get("type") == "title_generation":
            title = payload.get("title")
            return [], title.strip() if isinstance(title, str) and title.strip() else None
        output: list[str] = []
        value = payload.get("v")
        path = payload.get("p")
        if isinstance(value, dict):
            conversation_id = value.get("conversation_id")
            if isinstance(conversation_id, str) and conversation_id:
                state["conversation_id"] = conversation_id
            message = value.get("message")
            if isinstance(message, dict):
                recipient = message.get("recipient")
                if isinstance(recipient, str):
                    state["recipient"] = recipient
                if (
                    message.get("author", {}).get("role") == "assistant"
                    and isinstance(message.get("id"), str)
                    and message.get("id")
                ):
                    state["message_id"] = message["id"]
                    state["parent_message_id"] = message["id"]
            return output, None
        if isinstance(value, str):
            if state.get("recipient", "all") == "all" and path in (None, "/message/content/parts/0"):
                output.append(value)
            return output, None
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                if item.get("p") == "/message/content/parts/0" and state.get("recipient", "all") == "all":
                    token = item.get("v")
                    if isinstance(token, str):
                        output.append(token)
                elif item.get("p") == "/message/metadata" and state.get("recipient", "all") == "all":
                    finish_reason = item.get("v", {}).get("finish_details", {}).get("type")
                    if finish_reason:
                        state["finish_reason"] = finish_reason
            return output, None
        return output, None

    @staticmethod
    def _conversation_to_dict(
        conversation: ChatConversation | dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if isinstance(conversation, ChatConversation):
            return conversation.to_dict()
        if isinstance(conversation, dict):
            return dict(conversation)
        return None

    @staticmethod
    def _conversation_message_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts")
        if not isinstance(parts, list):
            return ""
        return "".join(part for part in parts if isinstance(part, str))

    @classmethod
    def _latest_assistant_from_conversation(
        cls,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        mapping = payload.get("mapping")
        if not isinstance(mapping, dict):
            return None, ""
        candidates: list[tuple[float, dict[str, Any], str]] = []
        for node in mapping.values():
            if not isinstance(node, dict):
                continue
            message = node.get("message")
            if not isinstance(message, dict):
                continue
            author = message.get("author")
            if not isinstance(author, dict) or author.get("role") != "assistant":
                continue
            text = cls._conversation_message_text(message)
            message_id = message.get("id")
            if not isinstance(message_id, str) or not text:
                continue
            create_time = message.get("create_time")
            candidates.append((float(create_time or 0), message, text))
        if not candidates:
            return None, ""
        _create_time, message, text = max(candidates, key=lambda item: item[0])
        return message, text

    @classmethod
    def _latest_message_any_from_conversation(
        cls,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        mapping = payload.get("mapping")
        if not isinstance(mapping, dict):
            return None, ""
        candidates: list[tuple[float, dict[str, Any], str]] = []
        for node in mapping.values():
            if not isinstance(node, dict):
                continue
            message = node.get("message")
            if not isinstance(message, dict):
                continue
            message_id = message.get("id")
            if not isinstance(message_id, str) or not message_id:
                continue
            create_time = message.get("create_time")
            candidates.append((float(create_time or 0), message, cls._conversation_message_text(message)))
        if not candidates:
            return None, ""
        _create_time, message, text = max(candidates, key=lambda item: item[0])
        return message, text

    @classmethod
    def _latest_confirm_action_leaf(
        cls,
        payload: dict[str, Any],
    ) -> tuple[str | None, str | None, str | None]:
        mapping = payload.get("mapping")
        if not isinstance(mapping, dict):
            return None, None, None
        candidates: list[tuple[float, str, str, str]] = []
        for node in mapping.values():
            if not isinstance(node, dict):
                continue
            message = node.get("message")
            if not isinstance(message, dict):
                continue
            author = message.get("author")
            role = author.get("role") if isinstance(author, dict) else ""
            if role != "tool" or node.get("children"):
                continue
            message_id = message.get("id")
            if not isinstance(message_id, str) or not message_id:
                continue
            metadata = message.get("metadata")
            if not isinstance(metadata, dict):
                continue
            jit_plugin_data = metadata.get("jit_plugin_data")
            if not isinstance(jit_plugin_data, dict):
                continue
            from_server = jit_plugin_data.get("from_server")
            if not isinstance(from_server, dict) or from_server.get("type") != "confirm_action":
                continue
            body = from_server.get("body")
            if not isinstance(body, dict):
                continue
            actions = body.get("actions")
            if not isinstance(actions, list):
                continue
            target_message_id: str | None = None
            for action in actions:
                if not isinstance(action, dict) or action.get("type") != "allow":
                    continue
                allow = action.get("allow")
                if isinstance(allow, dict) and isinstance(allow.get("target_message_id"), str):
                    target_message_id = allow["target_message_id"]
                    break
            if not target_message_id:
                continue
            target_node = mapping.get(target_message_id)
            if not isinstance(target_node, dict):
                continue
            target_message = target_node.get("message")
            if not isinstance(target_message, dict):
                continue
            recipient = target_message.get("recipient")
            if not isinstance(recipient, str) or not recipient:
                continue
            create_time = message.get("create_time")
            candidates.append((float(create_time or 0), message_id, target_message_id, recipient))
        if not candidates:
            return None, None, None
        _create_time, tool_id, target_message_id, recipient = max(candidates, key=lambda item: item[0])
        return tool_id, target_message_id, recipient

    @staticmethod
    def _build_client_allow_message(
        *,
        recipient: str,
        target_message_id: str,
        message_text: str = "",
    ) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "author": {"role": "tool", "name": recipient},
            "content": {"content_type": "text", "parts": [message_text]},
            "recipient": "all",
            "metadata": {
                "jit_plugin_data": {
                    "from_client": {
                        "type": "allow",
                        "target_message_id": target_message_id,
                        "remember_answer": False,
                    }
                }
            },
            "clientMetadata": {
                "completionSampleFinishTime": int(time.time() * 1000),
            },
        }

    def _get_conversation_payload(self, conversation_id: str) -> dict[str, Any]:
        headers = self._build_headers(
            {
                "accept": "application/json",
                "referer": f"{CHAT_URL.rstrip('/')}/c/{conversation_id}",
            }
        )
        status, data = self._json_request(
            "GET",
            CHAT_CONVERSATION_URL.format(conversation_id=conversation_id),
            None,
            headers,
        )
        if status >= 400:
            raise RequestError(f"conversation status={status}: {data}")
        if not isinstance(data, dict):
            raise RequestError("conversation response expected JSON object")
        return data

    def _list_recent_conversations(self, *, limit: int = 10) -> list[dict[str, Any]]:
        headers = self._build_headers({"accept": "application/json", "referer": CHAT_URL})
        status, data = self._json_request(
            "GET",
            f"{CHAT_CONVERSATIONS_URL}?offset=0&limit={max(1, limit)}&order=updated",
            None,
            headers,
        )
        if status >= 400:
            raise RequestError(f"conversations status={status}: {data}")
        if not isinstance(data, dict):
            raise RequestError("conversations response expected JSON object")
        items = data.get("items")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def _get_recent_conversation_summary(self, conversation_id: str) -> dict[str, Any] | None:
        for item in self._list_recent_conversations(limit=20):
            item_id = item.get("id")
            if isinstance(item_id, str) and item_id == conversation_id:
                return item
        return None

    @staticmethod
    def _normalize_reasoning_effort(reasoning_effort: str | None) -> str | None:
        normalized_effort = reasoning_effort.strip().lower() if isinstance(reasoning_effort, str) else None
        if normalized_effort in {"", "off", "none", "-"}:
            normalized_effort = None
        if normalized_effort not in {None, "standard", "extended"}:
            raise ValueError("reasoning_effort must be one of: standard, extended, off/none/-")
        return normalized_effort

    @staticmethod
    def _current_message_from_conversation(payload: dict[str, Any]) -> dict[str, Any] | None:
        current_node = payload.get("current_node")
        mapping = payload.get("mapping")
        if not isinstance(current_node, str) or not isinstance(mapping, dict):
            return None
        node = mapping.get(current_node)
        if not isinstance(node, dict):
            return None
        message = node.get("message")
        return message if isinstance(message, dict) else None

    @classmethod
    def _build_response_from_conversation_payload(
        cls,
        payload: dict[str, Any],
        *,
        fallback_conversation_id: str,
        fallback_user_id: str | None = None,
    ) -> ChatResponse:
        assistant_message, text = cls._latest_assistant_from_conversation(payload)
        current_message = cls._current_message_from_conversation(payload)
        selected_message = assistant_message or current_message or {}
        message_id = selected_message.get("id") if isinstance(selected_message.get("id"), str) else None
        metadata = selected_message.get("metadata") if isinstance(selected_message, dict) else None
        finish_reason = "stop"
        if isinstance(metadata, dict):
            finish_details = metadata.get("finish_details")
            if isinstance(finish_details, dict) and isinstance(finish_details.get("type"), str):
                finish_reason = finish_details["type"]
        return ChatResponse(
            text=text,
            conversation=ChatConversation(
                conversation_id=str(payload.get("conversation_id") or fallback_conversation_id),
                message_id=message_id,
                user_id=fallback_user_id,
                finish_reason=finish_reason,
                parent_message_id=message_id,
                is_thinking=False,
            ),
            metrics=ChatMetrics(),
        )

    def _is_conversation_idle(
        self,
        conversation_id: str,
        payload: dict[str, Any],
    ) -> bool:
        summary = self._get_recent_conversation_summary(conversation_id)
        if isinstance(summary, dict) and summary.get("async_status") is not None:
            return False
        current_message = self._current_message_from_conversation(payload)
        if not isinstance(current_message, dict):
            return False
        author = current_message.get("author")
        recipient = current_message.get("recipient")
        role = author.get("role") if isinstance(author, dict) else None
        return role == "assistant" and recipient == "all"

    def _poll_conversation_after_prepare(
        self,
        conversation_id: str,
        *,
        previous_message_id: str | None,
        timeout: float,
        interval: float,
    ) -> tuple[dict[str, Any] | None, str]:
        deadline = time.monotonic() + max(0.0, timeout)
        last_message: dict[str, Any] | None = None
        last_text = ""
        while True:
            payload = self._get_conversation_payload(conversation_id)
            message, text = self._latest_assistant_from_conversation(payload)
            if message is not None:
                last_message = message
                last_text = text
                message_id = message.get("id")
                if isinstance(message_id, str) and message_id != previous_message_id:
                    return message, text
            if time.monotonic() >= deadline:
                return last_message, last_text
            time.sleep(max(0.5, interval))

    def _stream_backend_payload(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        *,
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[str | None, str | None, str]:
        payload_path: str | None = None
        process: subprocess.Popen | None = None
        header_text = ""
        stderr_text = ""
        status = 0
        return_code = 0
        error_text: str | None = None
        raw_events: list[str] = []
        with tempfile.NamedTemporaryFile(delete=False) as header_file:
            header_path = header_file.name
        try:
            with tempfile.NamedTemporaryFile(delete=False) as payload_file:
                payload_file.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
                payload_path = payload_file.name
            command = self._build_curl_command(
                "POST",
                CHAT_BACKEND_URL,
                headers,
                header_path,
                payload_path,
                no_buffer=True,
            )
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            latest_conversation_id: str | None = None
            latest_message_id: str | None = None
            state = {
                "recipient": "all",
                "conversation_id": None,
                "message_id": None,
                "parent_message_id": None,
                "finish_reason": "stop",
            }
            full_chunks: list[str] = []
            assert process.stdout is not None
            for raw_line in iter(process.stdout.readline, b""):
                if not raw_line.startswith(b"data: "):
                    continue
                if raw_line.startswith(b"data: [DONE]"):
                    raw_events.append("[DONE]")
                    break
                raw_events.append(raw_line[6:].decode("utf-8", errors="replace").strip())
                try:
                    event_payload = json.loads(raw_line[6:])
                except ValueError:
                    continue
                tokens, _maybe_title = self._parse_event(event_payload, state)
                if isinstance(state.get("conversation_id"), str) and state["conversation_id"]:
                    latest_conversation_id = state["conversation_id"]
                if isinstance(state.get("message_id"), str) and state["message_id"]:
                    latest_message_id = state["message_id"]
                for token in tokens:
                    if not token:
                        continue
                    full_chunks.append(token)
                    if on_token is not None:
                        on_token(token)
                    self._emit_event(on_event, "assistant_token", token=token)
            if process.stderr is not None:
                stderr_text = process.stderr.read().decode("utf-8", errors="replace")
            return_code = process.wait()
            header_text = Path(header_path).read_text(encoding="utf-8", errors="replace")
            self._update_cookies_from_text(header_text)
            status = self._extract_status_code(header_text)
            if status >= 400:
                error_text = f"backend status={status}"
                raise RequestError(error_text)
            if return_code != 0:
                error_text = f"curl failed: {stderr_text.strip() or return_code}"
                raise RequestError(error_text)
            return latest_conversation_id, latest_message_id, "".join(full_chunks)
        finally:
            self._write_debug_trace(
                "stream",
                {
                    "method": "POST",
                    "url": CHAT_BACKEND_URL,
                    "request_headers": self._sanitize_headers_mapping(headers),
                    "request_body": self._trace_text_repr(json.dumps(payload, ensure_ascii=False)),
                    "response_status": status,
                    "response_headers": self._sanitize_header_lines(header_text),
                    "events": raw_events,
                    "stream_text": "".join(full_chunks) if "full_chunks" in locals() else "",
                    "stderr": stderr_text or None,
                    "return_code": return_code,
                    "error": error_text,
                },
            )
            self._cleanup_process(process)
            try:
                Path(header_path).unlink(missing_ok=True)
            except OSError:
                pass
            if payload_path:
                try:
                    Path(payload_path).unlink(missing_ok=True)
                except OSError:
                    pass

    def approve_pending_action(
        self,
        conversation: ChatConversation | dict[str, Any],
        *,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str | None = "extended",
        poll: bool = True,
        poll_timeout: float = DEFAULT_APPROVAL_POLL_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_APPROVAL_POLL_INTERVAL_SECONDS,
        timezone: str | None = None,
        timezone_offset_min: int | None = None,
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> ChatResponse:
        """Approve the latest pending tool action in a web conversation.

        Experimental best-effort browserless flow that mirrors the ChatGPT web
        UI approval card by synthesizing a
        ``jit_plugin_data.from_client.allow`` tool message and sending it
        through the same conversation backend.

        This helper is not a stable compatibility contract of the SDK and may
        require updates when ChatGPT web approval behavior changes.
        """
        conversation_dict = self._conversation_to_dict(conversation)
        if not isinstance(conversation_dict, dict):
            raise ValueError("conversation is required")
        conversation_id = conversation_dict.get("conversation_id")
        if not isinstance(conversation_id, str) or not conversation_id:
            raise ValueError("conversation.conversation_id is required")

        normalized_effort = self._normalize_reasoning_effort(reasoning_effort)
        conversation_payload = self._get_conversation_payload(conversation_id)
        tool_id, target_message_id, recipient = self._latest_confirm_action_leaf(conversation_payload)
        if not (tool_id and target_message_id and recipient):
            raise RequestError(
                f"pending tool approval not found in conversation payload: conversation_id={conversation_id}"
            )
        self._emit_event(
            on_event,
            "pending_approval_detected",
            conversation_id=conversation_id,
            pending_tool_id=tool_id,
            target_message_id=target_message_id,
            recipient=recipient,
        )

        prepare_payload: dict[str, Any] = {
            "action": "next",
            "fork_from_shared_post": False,
            "conversation_id": conversation_id,
            "parent_message_id": tool_id,
            "model": MODEL_ALIASES.get(model, model),
            "client_prepare_state": "none",
            "conversation_mode": {"kind": "primary_assistant"},
            "system_hints": [],
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "client_contextual_info": {"app_name": "chatgpt.com"},
        }
        if timezone_offset_min is not None:
            prepare_payload["timezone_offset_min"] = int(timezone_offset_min)
        if timezone:
            prepare_payload["timezone"] = timezone
        if normalized_effort is not None:
            prepare_payload["thinking_effort"] = normalized_effort

        prepare_headers = self._build_headers(
            {
                "accept": "application/json",
                "content-type": "application/json",
                "origin": CHAT_URL.rstrip("/"),
                "referer": f"{CHAT_URL.rstrip('/')}/c/{conversation_id}",
                "x-openai-target-path": "/backend-api/f/conversation/prepare",
                "x-openai-target-route": "/backend-api/f/conversation/prepare",
            }
        )
        started_at = time.perf_counter()
        status, data = self._json_request("POST", CHAT_CONVERSATION_PREPARE_URL, prepare_payload, prepare_headers)
        if status >= 400:
            raise RequestError(f"conversation prepare status={status}: {data}")
        if not isinstance(data, dict) or data.get("status") != "ok":
            raise RequestError(f"conversation prepare response expected status=ok: {data}")
        conduit_token = data.get("conduit_token")
        if not isinstance(conduit_token, str) or not conduit_token:
            raise RequestError("conversation prepare response missing conduit_token")
        self._emit_event(
            on_event,
            "approval_prepare_succeeded",
            conversation_id=conversation_id,
            pending_tool_id=tool_id,
        )

        requirements, proof_header = self._get_ready_requirements()
        stream_headers = self._build_headers(
            {
                "accept": "text/event-stream",
                "content-type": "application/json",
                "origin": CHAT_URL.rstrip("/"),
                "referer": f"{CHAT_URL.rstrip('/')}/c/{conversation_id}",
                "x-openai-target-path": "/backend-api/f/conversation",
                "x-openai-target-route": "/backend-api/f/conversation",
                "x-conduit-token": conduit_token,
                "x-oai-turn-trace-id": str(uuid.uuid4()),
                "openai-sentinel-chat-requirements-token": requirements.get("token"),
                "openai-sentinel-proof-token": proof_header,
                "openai-sentinel-turnstile-token": self.auth.turnstile_token
                if (requirements.get("turnstile") or {}).get("required")
                else None,
            }
        )
        stream_payload = dict(prepare_payload)
        stream_payload["client_prepare_state"] = "success"
        stream_payload["messages"] = [
            self._build_client_allow_message(
                recipient=recipient,
                target_message_id=target_message_id,
            )
        ]
        observed_conversation_id, _observed_message_id, streamed_text = self._stream_backend_payload(
            stream_payload,
            stream_headers,
            on_token=on_token,
            on_event=on_event,
        )
        self._emit_event(
            on_event,
            "approval_sent",
            conversation_id=conversation_id,
            pending_tool_id=tool_id,
            target_message_id=target_message_id,
        )
        if observed_conversation_id:
            conversation_id = observed_conversation_id

        text = streamed_text
        message_id = tool_id
        finish_reason = None
        if poll:
            message, text = self._poll_conversation_after_prepare(
                conversation_id,
                previous_message_id=tool_id,
                timeout=poll_timeout,
                interval=poll_interval,
            )
            if isinstance(message, dict):
                next_message_id = message.get("id")
                if isinstance(next_message_id, str) and next_message_id:
                    message_id = next_message_id
                metadata = message.get("metadata")
                if isinstance(metadata, dict):
                    finish_details = metadata.get("finish_details")
                    if isinstance(finish_details, dict):
                        finish_reason = finish_details.get("type")
            if message_id == tool_id:
                raise RequestError(
                    "approval polling timed out before a new assistant message appeared"
                )
            self._emit_event(
                on_event,
                "approval_completed",
                conversation_id=conversation_id,
                pending_tool_id=tool_id,
                message_id=message_id,
            )
        else:
            self._emit_event(
                on_event,
                "approval_completed",
                conversation_id=conversation_id,
                pending_tool_id=tool_id,
                message_id=message_id,
            )

        total_latency = time.perf_counter() - started_at
        return ChatResponse(
            text=text,
            conversation=ChatConversation(
                conversation_id=conversation_id,
                message_id=message_id,
                user_id=conversation_dict.get("user_id"),
                finish_reason=finish_reason or "stop",
                parent_message_id=message_id,
                is_thinking=False,
            ),
            metrics=ChatMetrics(total=total_latency),
        )

    def wait_and_approve_pending_actions(
        self,
        conversation: ChatConversation | dict[str, Any],
        *,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str | None = "extended",
        poll_timeout: float = DEFAULT_APPROVAL_POLL_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_APPROVAL_POLL_INTERVAL_SECONDS,
        pending_poll_interval: float = DEFAULT_PENDING_POLL_INTERVAL_SECONDS,
        settle_delay: float = DEFAULT_APPROVAL_SETTLE_DELAY_SECONDS,
        max_rounds: int = 0,
        timezone: str | None = None,
        timezone_offset_min: int | None = None,
        verify: Callable[[ChatResponse], bool] | None = None,
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> ChatResponse:
        """Repeatedly approve pending tool actions in a conversation.

        Experimental browserless helper built on top of
        :meth:`approve_pending_action`. With ``max_rounds=0`` the method waits
        indefinitely for new approval cards until interrupted. It stops on its
        own when the conversation becomes idle and no pending approvals remain.
        """
        conversation_dict = self._conversation_to_dict(conversation)
        if not isinstance(conversation_dict, dict):
            raise ValueError("conversation is required")
        conversation_id = conversation_dict.get("conversation_id")
        if not isinstance(conversation_id, str) or not conversation_id:
            raise ValueError("conversation.conversation_id is required")

        last_response = ChatResponse(
            text="",
            conversation=ChatConversation.from_dict(conversation_dict),
            metrics=ChatMetrics(),
        )
        round_index = 0
        waiting_announced = False
        while True:
            payload = self._get_conversation_payload(conversation_id)
            tool_id, target_message_id, recipient = self._latest_confirm_action_leaf(payload)
            if tool_id and target_message_id and recipient:
                waiting_announced = False
                round_index += 1
                self._emit_event(
                    on_event,
                    "approval_round_started",
                    conversation_id=conversation_id,
                    round_index=round_index,
                    pending_tool_id=tool_id,
                )
                last_response = self.approve_pending_action(
                    ChatConversation.from_dict(conversation_dict),
                    model=model,
                    reasoning_effort=reasoning_effort,
                    poll=True,
                    poll_timeout=poll_timeout,
                    poll_interval=poll_interval,
                    timezone=timezone,
                    timezone_offset_min=timezone_offset_min,
                    on_token=on_token,
                    on_event=on_event,
                )
                conversation_dict = last_response.conversation.to_dict()
                conversation_id = str(last_response.conversation.conversation_id or conversation_id)
                self._emit_event(
                    on_event,
                    "approval_round_finished",
                    conversation_id=conversation_id,
                    round_index=round_index,
                    message_id=last_response.conversation.message_id,
                )
                if max_rounds > 0 and round_index >= max_rounds:
                    return last_response
                if settle_delay > 0:
                    time.sleep(max(0.0, settle_delay))
                continue
            if max_rounds > 0 and round_index >= max_rounds:
                return last_response
            if self._is_conversation_idle(conversation_id, payload):
                final_response = self._build_response_from_conversation_payload(
                    payload,
                    fallback_conversation_id=conversation_id,
                    fallback_user_id=conversation_dict.get("user_id"),
                )
                self._emit_event(
                    on_event,
                    "conversation_idle",
                    conversation_id=conversation_id,
                    round_index=round_index,
                    message_id=final_response.conversation.message_id,
                )
                if verify is not None:
                    verified = bool(verify(final_response))
                    self._emit_event(
                        on_event,
                        "verification_completed",
                        conversation_id=conversation_id,
                        verified=verified,
                    )
                    if not verified:
                        raise RequestError("verification failed after workflow completion")
                return final_response
            if not waiting_announced:
                self._emit_event(
                    on_event,
                    "waiting_for_pending_approval",
                    conversation_id=conversation_id,
                    round_index=round_index,
                )
                waiting_announced = True
            time.sleep(max(0.5, pending_poll_interval))

    def send_and_auto_approve(
        self,
        prompt: str,
        *,
        model: str = DEFAULT_MODEL,
        system: str | None = None,
        web_search: bool = False,
        temporary: bool = False,
        reasoning_effort: str | None = "extended",
        conversation: ChatConversation | dict[str, Any] | None = None,
        media: Sequence[MediaItem] | None = None,
        on_token: Callable[[str], None] | None = None,
        new_chat_timeout: float = 60.0,
        pending_poll_interval: float = DEFAULT_PENDING_POLL_INTERVAL_SECONDS,
        settle_delay: float = DEFAULT_APPROVAL_SETTLE_DELAY_SECONDS,
        max_rounds: int = 0,
        poll_timeout: float = DEFAULT_APPROVAL_POLL_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_APPROVAL_POLL_INTERVAL_SECONDS,
        verify: Callable[[ChatResponse], bool] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> ChatResponse:
        """Send a prompt and then auto-approve follow-up tool actions.

        Experimental convenience wrapper for web-agent flows. It can start a new
        chat when ``conversation`` is omitted or continue an existing one when a
        conversation object is provided. The helper stops when the conversation
        becomes idle and no pending approvals remain.
        """
        before_ids: set[str] = set()
        conversation_dict = self._conversation_to_dict(conversation)
        if conversation_dict is None:
            conversation_dict = None
            for item in self._list_recent_conversations(limit=10):
                conversation_id = item.get("id")
                if isinstance(conversation_id, str) and conversation_id:
                    before_ids.add(conversation_id)

        send_response = self.send(
            prompt,
            model=model,
            system=system,
            web_search=web_search,
            temporary=temporary,
            reasoning_effort=reasoning_effort,
            conversation=conversation,
            media=media,
            on_token=on_token,
        )
        self._emit_event(
            on_event,
            "prompt_sent",
            conversation_id=send_response.conversation.conversation_id,
            message_id=send_response.conversation.message_id,
        )
        active_conversation = send_response.conversation
        if not active_conversation.conversation_id and conversation_dict is None:
            deadline = time.monotonic() + max(0.0, new_chat_timeout)
            while True:
                for item in self._list_recent_conversations(limit=10):
                    conversation_id = item.get("id")
                    if not isinstance(conversation_id, str) or not conversation_id:
                        continue
                    if conversation_id not in before_ids:
                        active_conversation = ChatConversation(
                            conversation_id=conversation_id,
                            message_id=send_response.conversation.message_id,
                            user_id=send_response.conversation.user_id,
                            finish_reason=send_response.conversation.finish_reason,
                            parent_message_id=send_response.conversation.parent_message_id,
                            is_thinking=send_response.conversation.is_thinking,
                        )
                        self._emit_event(
                            on_event,
                            "new_conversation_resolved",
                            conversation_id=conversation_id,
                        )
                        break
                if active_conversation.conversation_id:
                    break
                if time.monotonic() >= deadline:
                    raise RequestError("Timed out while waiting for the new conversation to appear")
                time.sleep(max(0.5, pending_poll_interval))

        if not active_conversation.conversation_id:
            raise RequestError("No conversation_id is available for auto-approval")

        return self.wait_and_approve_pending_actions(
            active_conversation,
            model=model,
            reasoning_effort=reasoning_effort,
            poll_timeout=poll_timeout,
            poll_interval=poll_interval,
            pending_poll_interval=pending_poll_interval,
            settle_delay=settle_delay,
            max_rounds=max_rounds,
            verify=verify,
            on_token=on_token,
            on_event=on_event,
        )

    def send(
        self,
        prompt: str,
        *,
        model: str = DEFAULT_MODEL,
        system: str | None = None,
        web_search: bool = False,
        temporary: bool = False,
        reasoning_effort: str | None = None,
        conversation: ChatConversation | dict[str, Any] | None = None,
        media: Sequence[MediaItem] | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> ChatResponse:
        normalized_effort = self._normalize_reasoning_effort(reasoning_effort)

        normalized_media = self._normalize_media_items(media)
        image_requests = self._upload_media_files(normalized_media) if normalized_media else None
        requirements, proof_header = self._get_ready_requirements()
        chat_token = requirements.get("token")
        if not isinstance(chat_token, str) or not chat_token:
            raise RequestError("chat-requirements token is missing")

        conversation_dict = self._conversation_to_dict(conversation)
        conversation_id = None
        parent_message_id = str(uuid.uuid4())
        user_id = None
        if isinstance(conversation_dict, dict):
            conversation_id = conversation_dict.get("conversation_id") or None
            parent_message_id = (
                conversation_dict.get("parent_message_id")
                or conversation_dict.get("message_id")
                or parent_message_id
            )
            user_id = conversation_dict.get("user_id")

        payload: dict[str, Any] = {
            "action": "next",
            "parent_message_id": parent_message_id,
            "model": MODEL_ALIASES.get(model, model),
            "conversation_mode": {"kind": "primary_assistant"},
            "enable_message_followups": False,
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "messages": self._create_messages(
                prompt,
                None if conversation_id else system,
                image_requests=image_requests,
                system_hints=["search"] if web_search else None,
            ),
        }
        if temporary:
            payload["history_and_training_disabled"] = True
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if web_search:
            payload["system_hints"] = ["search"]
        if normalized_effort is not None:
            payload["thinking_effort"] = normalized_effort

        headers = self._build_headers(
            {
                "accept": "text/event-stream",
                "content-type": "application/json",
                "openai-sentinel-chat-requirements-token": chat_token,
                "openai-sentinel-proof-token": proof_header,
                "openai-sentinel-turnstile-token": self.auth.turnstile_token
                if (requirements.get("turnstile") or {}).get("required")
                else None,
            }
        )
        state = {
            "recipient": "all",
            "conversation_id": conversation_id,
            "message_id": conversation_dict.get("message_id") if isinstance(conversation_dict, dict) else None,
            "parent_message_id": parent_message_id,
            "finish_reason": "stop",
        }
        first_token_latency: float | None = None
        last_token_latency: float | None = None
        full_chunks: list[str] = []
        title_update: str | None = None
        started_at = time.perf_counter()
        payload_path: str | None = None
        process: subprocess.Popen | None = None
        header_text = ""
        stderr_text = ""
        status = 0
        return_code = 0
        error_text: str | None = None
        raw_events: list[str] = []
        with tempfile.NamedTemporaryFile(delete=False) as header_file:
            header_path = header_file.name
        try:
            with tempfile.NamedTemporaryFile(delete=False) as payload_file:
                payload_file.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
                payload_path = payload_file.name
            command = self._build_curl_command(
                "POST",
                CHAT_BACKEND_URL,
                headers,
                header_path,
                payload_path,
                no_buffer=True,
            )
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            error_body: list[bytes] = []
            assert process.stdout is not None
            for raw_line in iter(process.stdout.readline, b""):
                if len(error_body) < 64:
                    error_body.append(raw_line)
                if not raw_line.startswith(b"data: "):
                    continue
                if raw_line.startswith(b"data: [DONE]"):
                    raw_events.append("[DONE]")
                    break
                raw_events.append(raw_line[6:].decode("utf-8", errors="replace").strip())
                try:
                    event_payload = json.loads(raw_line[6:])
                except ValueError:
                    continue
                tokens, maybe_title = self._parse_event(event_payload, state)
                if maybe_title and title_update is None:
                    title_update = maybe_title
                for token in tokens:
                    if not token:
                        continue
                    now = time.perf_counter()
                    if first_token_latency is None:
                        first_token_latency = now - started_at
                    last_token_latency = now - started_at
                    full_chunks.append(token)
                    if on_token is not None:
                        on_token(token)
            if process.stderr is not None:
                stderr_text = process.stderr.read().decode("utf-8", errors="replace")
            return_code = process.wait()
            header_text = Path(header_path).read_text(encoding="utf-8", errors="replace")
            self._update_cookies_from_text(header_text)
            status = self._extract_status_code(header_text)
            if status >= 400:
                body_text = b"".join(error_body).decode("utf-8", errors="replace")
                error_text = f"backend status={status}: {body_text[:300]}"
                raise RequestError(error_text)
            if return_code != 0:
                error_text = f"curl failed: {stderr_text.strip() or return_code}"
                raise RequestError(error_text)
        finally:
            self._write_debug_trace(
                "stream",
                {
                    "method": "POST",
                    "url": CHAT_BACKEND_URL,
                    "request_headers": self._sanitize_headers_mapping(headers),
                    "request_body": self._trace_text_repr(json.dumps(payload, ensure_ascii=False)),
                    "response_status": status,
                    "response_headers": self._sanitize_header_lines(header_text),
                    "events": raw_events,
                    "stream_text": "".join(full_chunks),
                    "stderr": stderr_text or None,
                    "return_code": return_code,
                    "error": error_text,
                },
            )
            self._cleanup_process(process)
            try:
                Path(header_path).unlink(missing_ok=True)
            except OSError:
                pass
            if payload_path:
                try:
                    Path(payload_path).unlink(missing_ok=True)
                except OSError:
                    pass

        total_latency = time.perf_counter() - started_at
        self.prefetched_requirements = None
        self.prefetched_proof_header = None
        self.prefetched_ts = 0.0
        return ChatResponse(
            text="".join(full_chunks),
            title=title_update,
            conversation=ChatConversation(
                conversation_id=state.get("conversation_id"),
                message_id=state.get("message_id") or state.get("parent_message_id"),
                user_id=user_id,
                finish_reason=state.get("finish_reason"),
                parent_message_id=state.get("parent_message_id"),
                is_thinking=False,
            ),
            metrics=ChatMetrics(
                first_token=first_token_latency,
                last_token=last_token_latency,
                total=total_latency,
            ),
        )
