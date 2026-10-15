"""Streaming curl opener for Qwen; secrets travel through stdin."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from email.parser import Parser
from pathlib import Path
from urllib.error import HTTPError


class CurlResponse:
    def __init__(self, request, timeout):
        self.temp = tempfile.TemporaryDirectory(prefix="cwa-qwen-")
        header_path = Path(self.temp.name) / "headers"
        config = [
            "silent",
            "show-error",
            "no-buffer",
            "max-time = " + str(timeout),
            "url = " + json.dumps(request.full_url),
            "request = " + json.dumps(request.method),
            "dump-header = " + json.dumps(str(header_path).replace("\\", "/")),
        ]
        for key, value in request.header_items():
            config.append("header = " + json.dumps(key + ": " + value))
        if request.data is not None:
            config.append("data = " + json.dumps(request.data.decode("utf-8")))
        curl = shutil.which("curl.exe") or shutil.which("curl")
        if not curl:
            self.temp.cleanup()
            raise OSError("curl is required")
        self.process = subprocess.Popen(
            [curl, "--config", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.process.stdin.write("\n".join(config).encode())
        self.process.stdin.close()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            text = (
                header_path.read_text(errors="replace") if header_path.exists() else ""
            )
            blocks = text.replace("\r\n", "\n").split("\n\n")
            complete = [
                b
                for b in blocks[:-1]
                if b.startswith("HTTP/")
                and "Connection established" not in b
                and " 100 " not in b
            ]
            if complete:
                block = complete[-1]
                self.status = int(block.splitlines()[0].split()[1])
                self.headers = Parser().parsestr("\n".join(block.splitlines()[1:]))
                if self.status >= 400:
                    self.close()
                    raise HTTPError(
                        request.full_url,
                        self.status,
                        "Qwen HTTP error",
                        self.headers,
                        None,
                    )
                return
            if self.process.poll() is not None:
                break
            time.sleep(0.01)
        self.close()
        raise OSError("Qwen curl response headers unavailable")

    def read(self, size=-1):
        return self.process.stdout.read(size)

    def __iter__(self):
        return iter(self.process.stdout)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait()
        self.process.stdout.close()
        self.temp.cleanup()


def curl_open(request, *, timeout):
    return CurlResponse(request, timeout)
