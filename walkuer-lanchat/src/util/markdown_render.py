from __future__ import annotations

import html
import re

import markdown

_URL_RE = re.compile(r"(?P<url>(https?://|www\.)[^\s<]+)")
_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")
_LINK_URL_RE = re.compile(r"\[[^\]]+\]\((?P<url>[^)]+)\)")
_HREF_RE = re.compile(r"""href=["'](?P<url>[^"']+)["']""")
_CODE_RE = re.compile(r"`[^`]*`")
_LONG_TOKEN_RE = re.compile(r"[^\s]{28,}")


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


def _insert_zwsp(token: str, chunk: int = 24) -> str:
    if len(token) <= chunk:
        return token
    zwsp = "\u200b"
    parts = [token[i:i + chunk] for i in range(0, len(token), chunk)]
    return zwsp.join(parts)


def _soft_wrap_long_tokens(text: str) -> str:
    if not text:
        return ""
    ranges = _find_protected_ranges(text)
    output: list[str] = []
    last = 0
    for match in _LONG_TOKEN_RE.finditer(text):
        if _in_ranges(match.start(), ranges):
            continue
        output.append(text[last:match.start()])
        output.append(_insert_zwsp(match.group(0)))
        last = match.end()
    output.append(text[last:])
    return "".join(output)


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("<") and url.endswith(">") and len(url) > 2:
        url = url[1:-1].strip()
    while url and url[-1] in ".,;:!?)]}":
        url = url[:-1]
    if url.startswith("www."):
        url = f"http://{url}"
    return url


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


def extract_first_url(text: str) -> str:
    if not text:
        return ""
    # Strip zero-width characters that can appear after copy/paste and break URL detection.
    text = (
        text.replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\ufeff", "")
    )
    for match in _LINK_URL_RE.finditer(text):
        url = _normalize_url(match.group("url") or "")
        if url:
            return url
    code_ranges: list[tuple[int, int]] = []
    for match in _CODE_RE.finditer(text):
        code_ranges.append((match.start(), match.end()))
    for match in _URL_RE.finditer(text):
        if _in_ranges(match.start(), code_ranges):
            continue
        url = _normalize_url(match.group("url") or "")
        if url:
            return url
    for match in _HREF_RE.finditer(text):
        url = _normalize_url(match.group("url") or "")
        if url:
            return url
    return ""


def render_markdown(text: str) -> str:
    try:
        text = _auto_link(text)
        text = _soft_wrap_long_tokens(text)
        rendered = markdown.markdown(
            text,
            extensions=["sane_lists", "nl2br"],
            output_format="html5",
        )
        return rendered.replace("\u200b", "<wbr>")
    except Exception:
        return "<pre>" + html.escape(text) + "</pre>"
