from __future__ import annotations

import argparse
import json

from .gemini_notebook_web import GeminiNotebookWebCapability


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Temporary PR16.4 Gemini Notebook URL-source live gate."
    )
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    capability = GeminiNotebookWebCapability(operation_timeout=args.timeout)
    result = capability.add_url_source(
        notebook=args.notebook,
        source_url=args.source_url,
        timeout=args.timeout,
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
