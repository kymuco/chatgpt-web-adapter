from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgpt_web_adapter.browserless_feasibility import base_feasibility_report, run_browserless_read_probe
from chatgpt_web_adapter.client import ChatGPTWebClient


def main() -> None:
    parser = argparse.ArgumentParser(description="PR8.2 read-only browserless feasibility probe")
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--auth-file", type=Path, default=Path("auth_data.json"))
    parser.add_argument("--sample-limit", type=int, default=5)
    args = parser.parse_args()

    client = ChatGPTWebClient(
        auth_file=args.auth_file,
        auto_refresh_auth=False,
        auto_login=False,
        auto_sentinel=False,
    )
    report = base_feasibility_report()
    result = run_browserless_read_probe(
        client,
        args.conversation,
        sample_limit=args.sample_limit,
    )
    report["live_read"] = result.to_dict()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
