# Ordinary Text Prepare / Conduit Contract Probe

PR7.11 isolates the current ChatGPT Web `conversation/prepare` boundary before
changing the SDK's ordinary `send()` path.

Current browser observations show an ordinary text prepare request shaped around:

- `POST /backend-api/f/conversation/prepare`
- `x-conduit-token: no-token` on the initial prepare call
- a user-message-shaped `partial_query`
- `client_prepare_state: success`
- a short-lived `conduit_token` in the response

This PR deliberately does **not** feed that token into normal `send()` yet. The
probe exists to verify the contract against a current authenticated session first.

## Run

```powershell
python .\examples\probe_prepare_contract.py `
  "https://chatgpt.com/c/<conversation-id>" `
  --output .\gpt56-prepare.json
```

The command attaches the existing conversation to recover the current model and
reasoning mode, then issues only the prepare request. It does not submit the turn
to `/backend-api/f/conversation`.

Expected evidence:

```json
{
  "prepare": {
    "status_code": 200,
    "status_ok": true,
    "conduit_token_present": true,
    "partial_query_present": true,
    "partial_query_text_recorded": false,
    "client_prepare_state": "success",
    "x_conduit_initial_mode": "no-token"
  },
  "verdict": "PREPARE_CONTRACT_OBSERVED"
}
```

## Privacy boundary

The report never records:

- prompt text or the `partial_query` body
- conduit-token values
- conversation/message ids
- auth/session tokens or cookies
- raw response bodies

Only structural booleans, status, safe response key names, and the prepare-state
label are retained.

## Exit criterion

`PREPARE_CONTRACT_OBSERVED` requires both a successful prepare response and the
presence of a conduit token. Once that is reproduced on a current live session,
a follow-up PR can wire prepare into ordinary `send()` and separately validate
Sentinel/Turnstile ordering and final conversation headers.

The explicit regression invariant for PR7.11 is that ordinary `send()` remains
unwired to the prepare boundary.
