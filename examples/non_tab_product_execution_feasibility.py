from __future__ import annotations

import json

from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnProvider
from chatgpt_web_adapter.non_tab_product_execution_feasibility import (
    base_non_tab_feasibility_report,
    run_current_write_surface_probe,
)


def main() -> None:
    report = {
        "pr": "PR8.2.5",
        **base_non_tab_feasibility_report(),
    }
    report["current_write_surface"] = run_current_write_surface_probe(
        BrowserNativeTurnProvider()
    ).to_dict()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
