from __future__ import annotations

import asyncio
import base64
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from .auth import CHAT_URL
from .exceptions import RequestError
from .sentinel_requirements import SENTINEL_FINALIZE_PATH
from .sentinel_transaction import (
    FinalizedSentinelBundle,
    _validate_finalize_response,
)
from .web_session import _sync_device_header


def _required_capture_value(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RequestError(
            f"SENTINEL_BROWSER_CAPTURE_INVALID: finalize {name} is missing",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_browser_capture",
        )
    return value.strip()


def _bundle_from_finalize_capture(
    request_payload: Any,
    response_status: int,
    response_payload: Any,
    *,
    acquired_monotonic: float | None = None,
    acquired_wallclock: float | None = None,
) -> FinalizedSentinelBundle:
    if not isinstance(request_payload, dict):
        raise RequestError(
            "SENTINEL_BROWSER_CAPTURE_INVALID: finalize request body is not an object",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_browser_capture",
        )
    proof_token = _required_capture_value(request_payload, "proofofwork")
    turnstile_token = _required_capture_value(request_payload, "turnstile")
    _required_capture_value(request_payload, "prepare_token")
    monotonic_now = time.monotonic() if acquired_monotonic is None else acquired_monotonic
    wallclock_now = time.time() if acquired_wallclock is None else acquired_wallclock
    requirements_token, expires_monotonic = _validate_finalize_response(
        int(response_status),
        response_payload,
        acquired_monotonic=float(monotonic_now),
        acquired_wallclock=float(wallclock_now),
    )
    return FinalizedSentinelBundle(
        requirements_token=requirements_token,
        proof_token=proof_token,
        turnstile_token=turnstile_token,
        acquired_monotonic=float(monotonic_now),
        expires_monotonic=expires_monotonic,
        source="browser_finalize_capture",
    )


def _sync_chatgpt_cookies(client: Any, browser_cookies: Any) -> None:
    target = getattr(getattr(client, "auth", None), "cookies", None)
    if not isinstance(target, dict) or not isinstance(browser_cookies, list):
        return
    for cookie in browser_cookies:
        domain = getattr(cookie, "domain", "")
        name = getattr(cookie, "name", None)
        value = getattr(cookie, "value", None)
        if (
            isinstance(domain, str)
            and domain.lstrip(".").lower().endswith("chatgpt.com")
            and isinstance(name, str)
            and isinstance(value, str)
        ):
            target[name] = value
    _sync_device_header(client)


class ZendriverSentinelBundleProvider:
    """Capture one unused bundle produced by the official ChatGPT page.

    The provider launches an isolated browser profile, seeds only the client's
    supplied ChatGPT cookies, observes the official finalize transaction in
    memory, and closes the browser. It never submits a chat message and never
    persists the captured one-shot credentials.
    """

    def __init__(
        self,
        *,
        timeout: float = 45.0,
        headless: bool = False,
        browser_executable_path: str | Path | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.timeout = float(timeout)
        self.headless = bool(headless)
        self.browser_executable_path = browser_executable_path

    def __call__(self, client: Any) -> FinalizedSentinelBundle:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._acquire(client))
        raise RequestError(
            "SENTINEL_BROWSER_PROVIDER_EVENT_LOOP: synchronous browser capture "
            "cannot run inside an active asyncio event loop",
            endpoint=SENTINEL_FINALIZE_PATH,
            request_stage="sentinel_bundle_provider",
        )

    @staticmethod
    def _import_zendriver() -> Any:
        try:
            import zendriver
        except ImportError as error:
            raise RequestError(
                "SENTINEL_BROWSER_PROVIDER_DEPENDENCY: install the optional "
                "browser extra with 'pip install chatgpt-web-adapter[browser]'",
                endpoint=SENTINEL_FINALIZE_PATH,
                request_stage="sentinel_bundle_provider",
            ) from error
        return zendriver

    async def _acquire(self, client: Any) -> FinalizedSentinelBundle:
        zendriver = self._import_zendriver()
        cdp = zendriver.cdp
        loop = asyncio.get_running_loop()
        captured: asyncio.Future[FinalizedSentinelBundle] = loop.create_future()
        finalize_requests: dict[Any, dict[str, Any]] = {}
        page: Any = None

        def on_request(event: Any, page: Any = None) -> None:
            request = getattr(event, "request", None)
            if request is None or getattr(request, "url", "") != (
                f"{CHAT_URL.rstrip('/')}{SENTINEL_FINALIZE_PATH}"
            ):
                return
            post_data = getattr(request, "post_data", None)
            if not isinstance(post_data, str):
                return
            try:
                payload = json.loads(post_data)
            except ValueError:
                return
            if isinstance(payload, dict):
                finalize_requests[event.request_id] = payload

        async def read_finalize_response(request_id: Any, response_status: int) -> None:
            if captured.done():
                return
            request_payload = finalize_requests.get(request_id)
            if request_payload is None:
                try:
                    post_data = await active_page.send(
                        cdp.network.get_request_post_data(request_id)
                    )
                    request_payload = json.loads(post_data)
                except Exception:
                    return
            body_response: tuple[str, bool] | None = None
            for _attempt in range(100):
                try:
                    body_response = await active_page.send(
                        cdp.network.get_response_body(request_id)
                    )
                    break
                except Exception:
                    await asyncio.sleep(0.05)
            if body_response is None:
                if not captured.done():
                    captured.set_exception(
                        RequestError(
                            "SENTINEL_BROWSER_CAPTURE_BODY: finalize response body "
                            "was not available from CDP",
                            endpoint=SENTINEL_FINALIZE_PATH,
                            request_stage="sentinel_browser_capture",
                        )
                    )
                return
            try:
                body, is_base64 = body_response
                if is_base64:
                    body = base64.b64decode(body).decode("utf-8")
                response_payload = json.loads(body)
                bundle = _bundle_from_finalize_capture(
                    request_payload,
                    response_status,
                    response_payload,
                )
            except Exception as error:
                if not captured.done():
                    captured.set_exception(error)
                return
            if not captured.done():
                captured.set_result(bundle)

        def on_response(event: Any, page: Any = None) -> None:
            response = getattr(event, "response", None)
            if response is None or getattr(response, "url", "") != (
                f"{CHAT_URL.rstrip('/')}{SENTINEL_FINALIZE_PATH}"
            ):
                return
            loop.create_task(
                read_finalize_response(
                    event.request_id,
                    int(getattr(response, "status", 0)),
                )
            )

        cookies = getattr(getattr(client, "auth", None), "cookies", None)
        if not isinstance(cookies, dict) or not cookies:
            raise RequestError(
                "SENTINEL_BROWSER_PROVIDER_AUTH: browser capture requires ChatGPT cookies",
                endpoint=SENTINEL_FINALIZE_PATH,
                request_stage="sentinel_bundle_provider",
            )

        with tempfile.TemporaryDirectory(prefix="chatgpt-web-adapter-") as profile_dir:
            browser = await zendriver.start(
                user_data_dir=profile_dir,
                headless=self.headless,
                browser_executable_path=self.browser_executable_path,
            )
            try:
                active_page = await browser.get("about:blank")
                active_page.add_handler(cdp.network.RequestWillBeSent, on_request)
                active_page.add_handler(cdp.network.ResponseReceived, on_response)
                await active_page.send(cdp.network.enable())
                cookie_params = [
                    cdp.network.CookieParam(
                        name=str(name),
                        value=str(value),
                        url=CHAT_URL,
                        secure=True,
                    )
                    for name, value in cookies.items()
                    if name is not None and value is not None
                ]
                await active_page.send(cdp.network.set_cookies(cookie_params))
                await active_page.get(CHAT_URL)

                # The page normally prefetches on its own. A reversible input
                # event nudges lazy clients without clicking the submit button.
                # Keep the probe in the editor until finalize completes: current
                # clients cancel the Sentinel transaction when input is cleared
                # immediately after the event.
                await asyncio.sleep(3.0)
                probe_input = None
                if not captured.done():
                    try:
                        probe_input = await active_page.select(
                            '#prompt-textarea, [contenteditable="true"]',
                            timeout=min(10.0, self.timeout),
                        )
                        # Zendriver/CDP emits trusted keyboard events. A synthetic
                        # InputEvent can start finalize without ever receiving a
                        # response on current ChatGPT clients.
                        await probe_input.send_keys(".")
                    except Exception:
                        probe_input = None
                bundle = await asyncio.wait_for(captured, timeout=self.timeout)
                if probe_input is not None:
                    try:
                        await probe_input.clear_input_by_deleting()
                    except Exception:
                        pass
                browser_cookies = await active_page.send(cdp.network.get_all_cookies())
                _sync_chatgpt_cookies(client, browser_cookies)
                return bundle
            except asyncio.TimeoutError as error:
                raise RequestError(
                    "SENTINEL_BROWSER_PROVIDER_TIMEOUT: official ChatGPT page did "
                    "not produce a finalized bundle before the timeout",
                    endpoint=SENTINEL_FINALIZE_PATH,
                    request_stage="sentinel_bundle_provider",
                ) from error
            finally:
                await browser.stop()
