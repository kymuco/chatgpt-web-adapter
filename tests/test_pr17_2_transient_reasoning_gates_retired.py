"""Production shipping must not retain PR17.2 diagnostic-only slider gates."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
RETIRED_PROBES = (
    "service_worker_reasoning_option_characterization.js",
    "service_worker_reasoning_slider_mutation.js",
    "service_worker_reasoning_slider_step_mutation.js",
    "service_worker_reasoning_slider_high_mutation.js",
)


def test_shipping_observability_does_not_load_retired_diagnostics() -> None:
    worker = (EXT / "service_worker_observability.js").read_text(encoding="utf-8")

    for name in RETIRED_PROBES:
        assert not (EXT / name).exists(), name
        assert f'importScripts("{name}")' not in worker

    for production_module in (
        "service_worker_model_profile_selection_pr8_10.js",
        "service_worker_selection_preparation.js",
        "service_worker_selection_lifecycle.js",
    ):
        assert (EXT / production_module).is_file(), production_module
        assert f'importScripts("{production_module}")' in worker
