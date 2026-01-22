from __future__ import annotations

import html
import re

import markdown

_URL_RE = re.compile(r"(?P<url>(https?://|www\.)[^\s<]+)")
_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")
_CODE_RE = re.compile(r"`[^`]*`")


def _find_protected_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for match in _CODE_RE.finditer(text):
        ranges.append((match.start(), match.end()))
    for match in _LINK_RE.finditer(text):
        ranges.append((match.start(), match.end()))
    return ranges


def _in_ranges(pos: int, ranges: list[tuple[int, int]]) -> bool:
    for start, end in ranges:
        if start <= pos < end:
            return True
    return False


def _break_url(text: str) -> str:
    zwsp = "\u200b"
    for ch in ["/", "?", "&", "=", "-", "_", "."]:
        text = text.replace(ch, f"{ch}{zwsp}")
    return text


def _auto_link(text: str) -> str:
    if not text:
        return ""
    ranges = _find_protected_ranges(text)
    output: list[str] = []
    last = 0
    for match in _URL_RE.finditer(text):
        if _in_ranges(match.start(), ranges):
            continue
        url = match.group("url")
        if not url:
            continue
        trailing = ""
        while url and url[-1] in ".,;:!?)]}":
            trailing = url[-1] + trailing
            url = url[:-1]
        if not url:
            continue
        output.append(text[last:match.start()])
        display = _break_url(url)
        href = url if not url.startswith("www.") else f"http://{url}"
        output.append(f"[{display}]({href})")
        output.append(trailing)
        last = match.end()
    output.append(text[last:])
    return "".join(output)


def render_markdown(text: str) -> str:
    try:
        text = _auto_link(text)
        return markdown.markdown(
            text,
            extensions=["sane_lists", "nl2br"],
            output_format="html5",
        )
    except Exception:
        return "<pre>" + html.escape(text) + "</pre>"
