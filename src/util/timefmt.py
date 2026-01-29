from __future__ import annotations

from datetime import datetime


def fmt_time(ts_ms: int) -> str:
    try:
        return datetime.fromtimestamp(ts_ms / 1000.0).strftime("%H:%M")
    except Exception:
        return "??:??"


def fmt_time_seconds(ts_seconds: float) -> str:
    try:
        return datetime.fromtimestamp(ts_seconds).strftime("%H:%M")
    except Exception:
        return "??:??"
