# Ordinary Text Prepare / Conduit Contract Probe

PR7.11 isolated the current ChatGPT Web `conversation/prepare` boundary before
changing the SDK's ordinary write path.

Current browser observations and the live PR7.11 probe show an ordinary text
prepare request shaped around:

- `POST /backend-api/f/conversation/prepare`
- `x-conduit-token: no-token` on the initial prepare call
- a user-message-shaped `partial_query`
- `client_prepare_state: success`
- a short-lived `conduit_token` in the response

The probe remains evidence-only: it never feeds the returned token into a final
conversation write.

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

## Exit outcome

The live PR7.11 run reproduced `PREPARE_CONTRACT_OBSERVED`: prepare returned HTTP
200 with `status=ok` and a conduit token while the report retained only structural
evidence.

PR7.11a therefore integrates this contract only into ordinary text writes to an
existing conversation. The direct new-chat `ChatGPTWebClient.send()` path and
multimodal writes remain outside that integration pending independent evidence.

The original PR7.11 regression remains useful: the evidence-only probe itself
still performs no final conversation write.
