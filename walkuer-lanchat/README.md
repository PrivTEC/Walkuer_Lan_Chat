# Walkür LAN Chat

<div align="center">
  <img src="assets/hero.svg" alt="Walkür LAN Chat Header" width="100%" />
  <p><strong>Globaler LAN-Chat für Windows — klicki-bunti, schnell, ohne Server.</strong></p>
  <p>Walkür Technology · Strategus One · Silvan Fülle</p>
  <p>
    <a href="API.md">API</a> ·
    <a href="#features">Features</a> ·
    <a href="#start">Start</a> ·
    <a href="LICENSE.md">Lizenz</a>
  </p>
</div>

Walkür LAN Chat ist ein winziges Windows-Tool für den lokalen Netzwerk-Chat: ein globaler Raum, automatische Discovery per UDP Multicast, Dateitransfer per lokalem HTTP, Tray-Modus, Markdown-Light — und ein dunkles Neon-UI im Walkür-Style. Kein Server, kein Cloud-Service, kein Internet. Einfach starten und loschatten.

<div align="center">
  <img src="assets/feature-strip.svg" alt="Features" width="100%" />
</div>

## Features
- Globaler LAN-Chat (Broadcast/Multicast): alle sehen denselben Raum.
- Auto-Discovery im Intranet (HELLO alle 2 Sekunden, Offline nach 8 Sekunden).
- Dateitransfer: Drag-and-Drop, Download per HTTP-URL, beliebige Dateitypen.
- Markdown-Light: **bold**, *italic*, `code`, Links, Listen.
- Tray-Modus: X = verstecken, neue Nachrichten mit Tray-Popup + Sound.
- Benutzername + Avatar, Themes, moderne Chat-Bubbles.
- Kein Admin nötig, Windows 10+ kompatibel.

## Warum es besonders ist
Kompakt, schnell, lokal. Für Teams, Studios, Werkstatt, Büro, LAN-Parties oder Intranet-Labs. Kein Setup, kein Account, keine Serverkosten. Einfach "klicky-bunti" und produktiv.

## Start
### Dev
1. `run_dev.bat`

### Build (EXE)
1. `build_exe.bat`
2. Ergebnis: `dist\WalkuerLanChat.exe`

## Nutzung
1. App auf zwei PCs im gleichen LAN starten.
2. Windows-Firewall kann beim ersten Start fragen: Zugriff erlauben.
3. Chatten, Dateien ziehen, fertig.

## Technik (Kurz)
- Python 3.11+, PySide6 (Qt)
- UDP Multicast Discovery + Global Chat
- Lokaler HTTP-Server nur für Attachments
- Nachrichtendedup mit UUID + Cache
- Tray via QSystemTrayIcon

## Suche & Keywords
LAN Chat, Windows LAN Chat, LAN Messenger, Intranet Chat, Local Chat, UDP Multicast, Peer-to-Peer Chat, Broadcast Chat, No Server Chat, File Transfer LAN, Windows Tray Chat, PySide6, Python 3.11, Walkür Technology, Strategus One, Silvan Fülle

## Attribution & Lizenz
Freie Nutzung für nicht-kommerzielle Zwecke. Kommerzielle Nutzung ist verboten.  
Wenn du Walkür LAN Chat nutzt oder weitergibst, ist die Attribution Pflicht:
- Walkür Technology
- Strategus One
- Silvan Fülle
- https://walkuer.tech
- https://strategus.one

Details in `LICENSE.md`.

## Manuelle Tests
- Zwei PCs im gleichen LAN:
  - Discovery zeigt online count = 2
  - Text senden, kommt bei beiden an
  - Datei senden, Download klappt
  - X -> Tray
  - Neue Nachricht -> Tray Popup + Beep
