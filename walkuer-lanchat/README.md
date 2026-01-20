# Walkür LAN Chat

Minimaler globaler LAN-Chat für Windows (PySide6). Kein Server, nur Multicast.

## Start (Dev)
1. `run_dev.bat`

## Build (EXE)
1. `build_exe.bat`
2. Ergebnis: `dist\WalkuerLanChat.exe`

## Nutzung
- App auf zwei PCs im gleichen LAN starten.
- Windows-Firewall kann beim ersten Start fragen: Zugriff erlauben.

## Manuelle Tests
- Zwei PCs im gleichen LAN:
  - Discovery zeigt online count = 2
  - Text senden, kommt bei beiden an
  - Datei senden, Download klappt
  - X -> Tray
  - Neue Nachricht -> Tray Popup + Beep
