from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
MANIFEST = EXT / "manifest.json"

IMPORT_SCRIPT = re.compile(r'^importScripts\("(?P<name>[^"]+)"\);$')
TOP_LEVEL_BARE_ASSIGNMENT = re.compile(r"^(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*=")
CAPTURED_HISTORICAL_ALIAS = re.compile(
    r"^(?:const|let|var)\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*(?:Prior|Original|Upstream|Historical)[A-Za-z0-9_$]*)"
    r"\s*=\s*(?P<target>[A-Za-z_$][A-Za-z0-9_$]*)\s*;$"
)

RETIRED_HISTORICAL_WORKERS = frozenset(
    {
        "service_worker_temporary_chat.js",
        "service_worker_temporary_snapshot_expression.js",
        "service_worker_temporary_chat_state_semantics.js",
        "service_worker_temporary_chat_ax_semantics.js",
        "service_worker_temporary_chat_semantic_notice.js",
        "service_worker_temporary_chat_turn_probe.js",
        "service_worker_temporary_chat_history_probe.js",
        "service_worker_temporary_chat_manual_ground_truth.js",
    }
)


def _active_imports(source: str) -> tuple[str, ...]:
    imports: list[str] = []
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line.startswith("importScripts("):
            continue
        match = IMPORT_SCRIPT.fullmatch(line)
        if match is None:
            raise RuntimeError(f"UNPARSEABLE_IMPORT_SCRIPTS:{line}")
        imports.append(match.group("name"))
    return tuple(imports)


def production_worker_graph(extension_dir: Path = EXT) -> tuple[str, ...]:
    manifest_path = extension_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entrypoint = manifest.get("background", {}).get("service_worker")
    if not isinstance(entrypoint, str) or not entrypoint:
        raise RuntimeError("BACKGROUND_SERVICE_WORKER_REQUIRED")

    queue: deque[str] = deque([entrypoint])
    seen: set[str] = set()

    while queue:
        name = queue.popleft()
        if name in seen:
            continue

        path = extension_dir / name
        if not path.is_file():
            raise RuntimeError(f"WORKER_IMPORT_MISSING:{name}")

        seen.add(name)
        source = path.read_text(encoding="utf-8")
        for imported in _active_imports(source):
            if imported not in seen:
                queue.append(imported)

    return tuple(sorted(seen))


def source_ownership_debt(name: str, source: str) -> tuple[str, ...]:
    debt: list[str] = []
    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        if raw_line != raw_line.lstrip():
            continue

        assignment = TOP_LEVEL_BARE_ASSIGNMENT.match(raw_line)
        if assignment is not None:
            debt.append(
                f"{name}:{line_number}:top-level-rebinding:{assignment.group('name')}"
            )

        alias = CAPTURED_HISTORICAL_ALIAS.fullmatch(raw_line)
        if alias is not None:
            debt.append(
                f"{name}:{line_number}:captured-historical-alias:"
                f"{alias.group('name')}->{alias.group('target')}"
            )

    return tuple(debt)


def production_ownership_debt(extension_dir: Path = EXT) -> tuple[str, ...]:
    graph = production_worker_graph(extension_dir)
    debt: list[str] = []

    retired_present = sorted(
        name for name in RETIRED_HISTORICAL_WORKERS if (extension_dir / name).exists()
    )
    for name in retired_present:
        debt.append(f"{name}:retired-historical-worker-present")

    for name in graph:
        source = (extension_dir / name).read_text(encoding="utf-8")
        debt.extend(source_ownership_debt(name, source))

    return tuple(sorted(debt))


def main() -> int:
    graph = production_worker_graph()
    debt = production_ownership_debt()

    print(f"browser worker production graph: {len(graph)} files")
    if debt:
        print("browser worker ownership closure gate failed:")
        for item in debt:
            print(f"- {item}")
        return 1

    print(
        "browser worker ownership closure gate passed: "
        "zero top-level rebinding, zero captured composition aliases, "
        "retired Temporary characterization source remains absent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
