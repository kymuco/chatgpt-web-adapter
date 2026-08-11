from __future__ import annotations

import json

from chatgpt_web_adapter.auth_store import persist_auth_data
from chatgpt_web_adapter.types import AuthData


def test_persist_auth_data_keeps_structured_browser_cookies(tmp_path) -> None:
    path = tmp_path / "auth.json"
    auth = AuthData(
        accessToken="not.a.jwt",
        cookies={"session.0": "chunk"},
        browserCookies=[
            {
                "name": "session.0",
                "value": "chunk",
                "domain": ".chatgpt.com",
                "path": "/",
                "secure": True,
            }
        ],
    )

    persist_auth_data(auth, path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    loaded = AuthData.from_json(path)

    assert saved["browserCookies"][0]["domain"] == ".chatgpt.com"
    assert loaded.browserCookies == saved["browserCookies"]
