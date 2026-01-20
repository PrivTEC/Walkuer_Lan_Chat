from __future__ import annotations

from datetime import datetime


def fmt_time(ts_ms: int) -> str:
    try:
        return datetime.fromtimestamp(ts_ms / 1000.0).strftime("%H:%M")
    except Exception:
        return "??:??"
