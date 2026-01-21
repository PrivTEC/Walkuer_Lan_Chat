from __future__ import annotations

try:
    import winsound
except Exception:  # pragma: no cover - winsound missing on non-Windows
    winsound = None


def play_notification(enabled: bool) -> None:
    if not enabled or winsound is None:
        return
    try:
        winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
        return
    except Exception:
        pass
    try:
        winsound.Beep(640, 50)
        winsound.Beep(520, 70)
    except Exception:
        try:
            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass
