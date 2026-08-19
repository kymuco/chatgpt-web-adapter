from __future__ import annotations

import argparse
import json

from chatgpt_web_adapter.browserless_product_execution_closure import (
    product_execution_closure_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PR8.2.3 supported non-browser ChatGPT product execution closure"
    )
    parser.add_argument(
        "--native-inventory",
        action="store_true",
        help="read-only inventory of installed ChatGPT AppX packages and Codex CLI presence",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            product_execution_closure_report(
                include_native_inventory=args.native_inventory,
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
