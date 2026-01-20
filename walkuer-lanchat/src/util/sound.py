from __future__ import annotations

try:
    import winsound
except Exception:  # pragma: no cover - winsound missing on non-Windows
    winsound = None


def play_notification(enabled: bool) -> None:
    if not enabled or winsound is None:
        return
    try:
        winsound.Beep(520, 60)
        winsound.Beep(660, 80)
    except Exception:
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
