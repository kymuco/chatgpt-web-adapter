from __future__ import annotations

import argparse
import json
from urllib.parse import urlparse

if __package__:
    from .pr13_1_conversation_files_identity_probe import _conversation_id, run_probe
else:
    from pr13_1_conversation_files_identity_probe import _conversation_id, run_probe

_ALLOWED_CHATGPT_HOSTS = frozenset({"chatgpt.com", "www.chatgpt.com"})


def conversation_id_from_selector(value: str) -> str:
    """Accept either one explicit conversation id or a ChatGPT conversation URL."""

    text = value.strip()
    if "://" not in text:
        return _conversation_id(text)

    parsed = urlparse(text)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_CHATGPT_HOSTS:
        raise ValueError("CHATGPT_CONVERSATION_URL_REQUIRED")

    parts = [part for part in parsed.path.split("/") if part]
    candidates = [
        parts[index + 1] for index, part in enumerate(parts[:-1]) if part == "c"
    ]
    if len(candidates) != 1:
        raise ValueError("CHATGPT_CONVERSATION_URL_REQUIRED")
    return _conversation_id(candidates[0])


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the read-only PR13.1 conversation-files identity probe using either "
            "a saved ChatGPT conversation URL or a raw conversation id."
        )
    )
    parser.add_argument(
        "--conversation",
        required=True,
        help="Raw conversation id or https://chatgpt.com/.../c/<conversation-id> URL.",
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    try:
        conversation_id = conversation_id_from_selector(args.conversation)
    except ValueError as exc:
        parser.error(str(exc))

    report = run_probe(
        conversation_id=conversation_id,
        expected_head=args.expected_head,
        timeout=args.timeout,
    )
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))

    completed_characterizations = {
        "AUTHENTICATION_REQUIRED",
        "ACCESS_CHALLENGED",
        "ENDPOINT_ABSENT_OR_NOT_VISIBLE",
        "FILES_ENDPOINT_HTTP_ERROR",
        "UNRECOGNIZED_FILES_RESPONSE_SHAPE",
        "EMPTY_FILE_COLLECTION_OBSERVED",
        "NON_OBJECT_FILE_RECORD_OBSERVED",
        "FILE_RECORDS_WITHOUT_EXPLICIT_IDENTITY",
        "DUPLICATE_EXPLICIT_IDENTITY_CANDIDATE_OBSERVED",
        "EXPLICIT_PRODUCT_IDENTITY_CANDIDATES_OBSERVED",
    }
    return 0 if report.get("characterization") in completed_characterizations else 1


if __name__ == "__main__":
    raise SystemExit(main())
