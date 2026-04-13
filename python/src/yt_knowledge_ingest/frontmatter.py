from __future__ import annotations

import re
from dataclasses import dataclass

_FM_RE = re.compile(
    r"^---\s*\n(?P<body>.*?)\n---\s*\n(?P<rest>.*)",
    re.DOTALL | re.MULTILINE,
)


@dataclass
class HeaderStatus:
    status: str | None
    raw_yaml: str


def parse_frontmatter_markdown(text: str) -> HeaderStatus:
    m = _FM_RE.match(text)
    if not m:
        return HeaderStatus(None, "")
    body = m.group("body")
    status = None
    for line in body.splitlines():
        if line.lower().startswith("status:"):
            status = line.split(":", 1)[1].strip().strip('"').strip("'")
            break
    return HeaderStatus(status, body)


def build_markdown(
    *,
    source_url: str,
    playlist: str,
    slug: str,
    status: str,
    error: str,
    body: str,
) -> str:
    err = error.replace("\n", " ")
    lines = [
        "---",
        f'source_url: "{source_url}"',
        f'playlist: "{playlist}"',
        f'slug: "{slug}"',
        f"status: {status}",
        f'error: "{err}"',
        "---",
        "",
        body.strip(),
        "",
    ]
    return "\n".join(lines)


def is_ok_skip_existing(content: str) -> bool:
    hs = parse_frontmatter_markdown(content)
    return (hs.status or "").lower() == "ok"
