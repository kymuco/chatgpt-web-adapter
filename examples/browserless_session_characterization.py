from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgpt_web_adapter.browserless_session_characterization import (
    characterize_browserless_session,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PR8.2.1 browserless session longevity and refresh characterization"
    )
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument(
        "--refresh-probe",
        action="store_true",
        help="prove session-cookie-only access-token refresh without launching a browser",
    )
    parser.add_argument(
        "--no-persist-refresh",
        action="store_true",
        help="do not atomically persist refreshed credentials (not recommended for a live auth file)",
    )
    args = parser.parse_args()

    report = characterize_browserless_session(
        args.conversation,
        auth_file=args.auth_file,
        sample_limit=args.sample_limit,
        refresh_probe=args.refresh_probe,
        persist_refresh=not args.no_persist_refresh,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
