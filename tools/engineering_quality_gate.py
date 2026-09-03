from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_PREFIX = "src/chatgpt_web_adapter/"
LEGACY_PRODUCTION_NAME = re.compile(r"(?:_pr\d+|repair)", re.IGNORECASE)
MODULE_ATTRIBUTE_ASSIGNMENT = re.compile(
    r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\s*="
)
TOP_LEVEL_SETATTR = re.compile(r"^setattr\(")
TOP_LEVEL_INSTALL = re.compile(r"^install_[A-Za-z0-9_]\w*\(")
ALLOW_MARKER = "engineering-quality: allow-import-time-mutation"


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _resolve_base_ref(value: str | None) -> str:
    candidate = (value or "").strip()
    if candidate and set(candidate) != {"0"}:
        return candidate
    return "HEAD^"


def _added_production_files(base_ref: str) -> list[str]:
    output = _git(
        "diff",
        "--name-only",
        "--diff-filter=A",
        f"{base_ref}...HEAD",
        "--",
        "src/chatgpt_web_adapter",
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def _new_import_time_mutations(base_ref: str) -> list[str]:
    patch = _git(
        "diff",
        "--unified=0",
        f"{base_ref}...HEAD",
        "--",
        "src/chatgpt_web_adapter",
    )
    violations: list[str] = []
    current_path: str | None = None

    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            current_path = line.removeprefix("+++ b/")
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue

        addition = line[1:]
        if not addition or addition[0].isspace() or ALLOW_MARKER in addition:
            continue
        if (
            MODULE_ATTRIBUTE_ASSIGNMENT.match(addition)
            or TOP_LEVEL_SETATTR.match(addition)
            or TOP_LEVEL_INSTALL.match(addition)
        ):
            violations.append(f"{current_path or '<unknown>'}: {addition}")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prevent new research-era production topology and import-time mutation debt."
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="Git base SHA/ref. Defaults to HEAD^ when omitted or unavailable.",
    )
    args = parser.parse_args()
    base_ref = _resolve_base_ref(args.base_ref)

    violations: list[str] = []
    for path in _added_production_files(base_ref):
        suffix = Path(path).suffix.lower()
        if suffix in {".py", ".js"} and LEGACY_PRODUCTION_NAME.search(Path(path).name):
            violations.append(
                f"new production module uses research-era PR/repair naming: {path}"
            )

    for mutation in _new_import_time_mutations(base_ref):
        violations.append(f"new module-level runtime mutation: {mutation}")

    if violations:
        print("engineering quality gate failed:")
        for violation in violations:
            print(f"- {violation}")
        print(
            "Existing legacy debt is grandfathered, but new debt is blocked. "
            "Refactor through explicit composition instead."
        )
        return 1

    print(
        "engineering quality gate passed: no new PR/repair-named production modules "
        "or module-level runtime mutation debt"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
