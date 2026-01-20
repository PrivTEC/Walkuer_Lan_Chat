from __future__ import annotations

import html

import markdown


def render_markdown(text: str) -> str:
    try:
        return markdown.markdown(
            text,
            extensions=["sane_lists", "nl2br"],
            output_format="html5",
        )
    except Exception:
        return "<pre>" + html.escape(text) + "</pre>"
