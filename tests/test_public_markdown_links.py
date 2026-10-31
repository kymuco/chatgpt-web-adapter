"""Check current public Markdown navigation without a Markdown dependency.

Historical engineering records are not first-contact entrypoints; validate the
active public guides and any local Markdown targets they reference.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_GUIDES = (
    "README.md",
    "AGENTS.md",
    "llms.txt",
    "STATUS.md",
    "ROADMAP.md",
    "USAGE.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "QWEN.md",
    "QWEN.ru.md",
    "docs/README.md",
    "docs/quickstart.md",
    "docs/agent_integration.md",
    "docs/standalone_send_cli.md",
    "docs/authentication.md",
    "docs/browserless_http_sdk.md",
    "docs/building_on_top.md",
    "docs/capabilities.md",
    "docs/providers.md",
    "docs/troubleshooting.md",
)
MARKDOWN_LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$")
HTML_ANCHOR = re.compile(r'<a\s+[^>]*\b(?:id|name)=["\x27]([^"\x27]+)["\x27]', re.I)


def _outside_fences(text: str) -> str:
    visible: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            candidate = marker.group(1)
            if fence is None:
                fence = candidate
            elif candidate[0] == fence[0] and len(candidate) >= len(fence):
                fence = None
            visible.append("")
        else:
            visible.append(line if fence is None else "")
    return "\n".join(visible)


def _github_slug(heading: str) -> str:
    heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
    heading = re.sub(r"<[^>]*>", "", heading)
    heading = heading.replace("`", "")
    heading = re.sub(r"[^\w -]", "", heading.lower())
    return re.sub(r"\s", "-", heading.strip())


def _anchors(text: str) -> set[str]:
    visible = _outside_fences(text)
    counts: dict[str, int] = {}
    anchors: set[str] = set(HTML_ANCHOR.findall(visible))
    for line in visible.splitlines():
        match = HEADING.match(line)
        if not match:
            continue
        stem = _github_slug(match.group(1))
        index = counts.get(stem, 0)
        counts[stem] = index + 1
        anchors.add(f"{stem}-{index}" if index else stem)
    return anchors


def _broken_links(source: Path, text: str, root: Path) -> list[str]:
    errors: list[str] = []
    for match in MARKDOWN_LINK.finditer(_outside_fences(text)):
        target_url = match.group(1).strip()
        if target_url.startswith("<"):
            target_url = target_url.split(">", 1)[0][1:]
        else:
            target_url = target_url.split(' "', 1)[0]
        parsed = urlsplit(target_url)
        if parsed.scheme or parsed.netloc:
            continue
        path = unquote(parsed.path)
        fragment = unquote(parsed.fragment)
        destination = (source.parent / path).resolve() if path else source.resolve()
        if not destination.is_relative_to(root.resolve()):
            errors.append(f"{source.name}: link escapes repository: {target_url}")
        elif not destination.is_file():
            errors.append(f"{source.name}: missing file: {target_url}")
        elif fragment and destination.suffix.lower() in {".md", ".txt"}:
            if fragment not in _anchors(destination.read_text(encoding="utf-8")):
                errors.append(f"{source.name}: missing anchor: {target_url}")
    return errors


def test_public_document_links_resolve() -> None:
    problems: list[str] = []
    for name in PUBLIC_GUIDES:
        source = ROOT / name
        assert source.is_file(), name
        problems.extend(_broken_links(source, source.read_text(encoding="utf-8"), ROOT))
    assert not problems, "\n".join(problems)


def test_anchor_checker_rejects_stale_links(tmp_path: Path) -> None:
    doc = tmp_path / "README.md"
    content = "# Secondary browser-owned Python example\n\n[Old](#production-python-example)\n"
    doc.write_text(content, encoding="utf-8")
    assert _broken_links(doc, content, tmp_path) == [
        "README.md: missing anchor: #production-python-example"
    ]


def test_github_duplicate_heading_suffixes_and_code_blocks() -> None:
    sample = (
        "## Hello, world!\n## Hello, world!\n"
        "~~~markdown\n## Hidden heading\n[bad](#hidden-heading)\n~~~\n"
    )
    assert _anchors(sample) == {"hello-world", "hello-world-1"}
