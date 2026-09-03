from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def main() -> int:
    node = shutil.which("node")
    if node is None:
        raise SystemExit("Node.js is required for extension syntax validation")

    files = sorted(EXTENSION.glob("*.js"))
    if not files:
        raise SystemExit("no extension JavaScript files found")

    for path in files:
        subprocess.run(
            [node, "--check", str(path)],
            check=True,
            cwd=ROOT,
        )

    print(f"validated JavaScript syntax for {len(files)} extension files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
