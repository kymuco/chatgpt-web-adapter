# PR8.2.2 — Browserless Session Renewal Replication, Long-Lived Credential Boundary and Browser-Reentry Failure Taxonomy

PR8.2.2 replicates the PR8.2.1 browserless session-refresh result across repeated cold-reuse cycles without exercising the ChatGPT product write path.

## Goal

Prove that saved ChatGPT session state is reusable as a standalone credential substrate across repeated cycles:

1. reload saved auth from disk;
2. remove the access token only from in-memory auth;
3. recover through the existing session endpoint;
4. persist refreshed auth atomically;
5. create a fresh client from the persisted auth file;
6. read the same conversation canonically;
7. repeat.

A successful in-memory refresh is not sufficient. Every cycle must persist successfully and then survive a fresh-client cold read.

## Positive verdict

`BROWSERLESS_SESSION_RENEWAL_REPLICATION_PROVEN`

The verdict requires all requested bounded cycles to complete with:

- refresh success;
- persistence success;
- fresh-client canonical read success;
- reusable session state still present at the end.

Session-token rotation and session-expiry extension are recorded as evidence but are not mandatory on every server response.

## Failure taxonomy

Only these failures establish a need for browser re-entry:

- `NO_REUSABLE_SESSION` — no reusable session credential is available.
- `SESSION_REFRESH_REJECTED_401_403` — the server explicitly rejects the reusable session.

These failures do **not** establish browser re-entry:

- `LOCAL_AUTH_STATE_OR_PERSISTENCE_FAILURE`
- `TRANSPORT_OR_NETWORK_FAILURE`
- `POST_REFRESH_COLD_RESTART_READ_FAILURE`

They require local/transport diagnosis rather than an automatic browser launch.

## Longitudinal gate

`REAL_POST_ACCESS_EXPIRY_RENEWAL_DEFERRED`

PR8.2.2 does not modify JWT expiry, fake wall-clock time, or otherwise simulate server-side access-token expiration. The real post-expiry renewal gate remains deferred until a naturally expired access token can be tested with the browser closed.

## Governance

This PR does not:

- send ChatGPT product turns;
- use the browser-native turn bridge;
- perform interactive login;
- expand Sentinel/challenge/protection logic;
- emit access-token or session-cookie values;
- claim that browserless consumer ChatGPT product writes are supported.

The replication probe is bounded to 1–10 cycles, with 3 cycles as the default.

## Live probe

With Chrome fully closed:

```powershell
python examples/browserless_session_renewal_replication.py `
  --conversation <conversation-id> `
  --cycles 3
```

A strong live result has:

- `verdict = BROWSERLESS_SESSION_RENEWAL_REPLICATION_PROVEN`
- `attempted_cycles = requested_cycles`
- `successful_cycles = requested_cycles`
- `persistence_count = requested_cycles`
- `cold_restart_read_count = requested_cycles`
- `long_lived_session_reusable_after_replication = true`
