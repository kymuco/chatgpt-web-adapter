"""Offline tests for the Direct HTTP dispatch-identity callback."""
import json
import sqlite3
from contextlib import closing, nullcontext
from pathlib import Path
from threading import RLock

import pytest
from test_client import _build_client

import chatgpt_web_adapter.browserless_http as http
import chatgpt_web_adapter.conversation_prepare as prepare
import chatgpt_web_adapter.sentinel_bundle as sentinel
from chatgpt_web_adapter import legacy_client_core as core
from chatgpt_web_adapter.browserless_http import BrowserlessHTTPClient


class StopBeforePost(Exception):
    pass


def _client(monkeypatch, prepared):
    client = object.__new__(BrowserlessHTTPClient)
    client.__dict__.update(_build_client().__dict__)
    client._browserless_lock = RLock()
    client._browserless_sending = False
    client.last_timing = {}
    client.set_sentinel_bundle_provider = lambda _: None
    monkeypatch.setattr(http, 'bootstrap_web_session', lambda _: True)
    monkeypatch.setattr(http, 'suppress_web_session_debug_trace', nullcontext)
    monkeypatch.setattr(sentinel, 'prepared_send_active', lambda: prepared)
    monkeypatch.setattr(client, '_get_ready_requirements', lambda: ({'token': 'synthetic'}, None))
    monkeypatch.setattr(client, 'start_sentinel_bundle_refill', lambda **kwargs: None)
    prepared_ids = []
    def fake_prepare(_client, payload, _headers):
        prepared_ids.append(payload['partial_query']['id'])
        return 200, {'status': 'ok', 'conduit_token': 'synthetic'}
    monkeypatch.setattr(prepare, '_prepare_json_request', fake_prepare)
    return client, prepared_ids


@pytest.mark.parametrize('prepared', [False, True])
def test_identity_persisted_before_actual_curl_boundary(monkeypatch, tmp_path, prepared):
    client, prepared_ids = _client(monkeypatch, prepared)
    path = tmp_path / 'test.sqlite'
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE identity (message_id TEXT NOT NULL)')
    def persist(identity):
        assert set(identity) == {'conversation_id', 'user_message_id', 'parent_message_id', 'temporary'}
        assert identity['conversation_id'] == 'synthetic-chat'
        assert 'private synthetic prompt' not in repr(identity)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('INSERT INTO identity VALUES (?)', (identity['user_message_id'],))
    calls = []
    def intercept(command, **kwargs):
        calls.append(1)
        arg = command[command.index('--data-binary') + 1]
        payload = json.loads(Path(arg[1:]).read_text(encoding='utf-8'))
        message_id = [m['id'] for m in payload['messages'] if m['author']['role'] == 'user'][0]
        with closing(sqlite3.connect(path)) as db:
            assert db.execute('SELECT message_id FROM identity').fetchone()[0] == message_id
        if prepared:
            assert prepared_ids == [message_id]
        raise StopBeforePost()
    monkeypatch.setattr(core.subprocess, 'Popen', intercept)
    with pytest.raises(StopBeforePost):
        client.send('private synthetic prompt', conversation={'conversation_id': 'synthetic-chat', 'parent_message_id': 'synthetic-parent'}, on_dispatch_identity=persist)
    assert calls == [1]
    assert b'private synthetic prompt' not in path.read_bytes()


@pytest.mark.parametrize('prepared', [False, True])
def test_storage_error_stops_before_actual_curl_boundary(monkeypatch, prepared):
    client, _ = _client(monkeypatch, prepared)
    calls = []
    monkeypatch.setattr(core.subprocess, 'Popen', lambda *args, **kwargs: calls.append(1))
    def fail(_identity):
        raise OSError('synthetic storage failure')
    with pytest.raises(OSError, match='storage failure'):
        client.send('synthetic', conversation={'conversation_id': 'synthetic-chat', 'parent_message_id': 'synthetic-parent'}, on_dispatch_identity=fail)
    assert calls == []
