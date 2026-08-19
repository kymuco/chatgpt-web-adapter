from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgpt_web_adapter.browserless_session_renewal_replication import (
    DEFAULT_CYCLES,
    replication_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PR8.2.2 browserless session renewal replication probe"
    )
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--cycles", type=int, default=DEFAULT_CYCLES)
    parser.add_argument("--sample-limit", type=int, default=5)
    args = parser.parse_args()

    report = replication_report(
        args.conversation,
        auth_file=args.auth_file,
        cycles=args.cycles,
        sample_limit=args.sample_limit,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
