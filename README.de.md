# Walkür LAN Chat

<div align="center">
  <img src="assets/hero.svg" alt="Walkür LAN Chat Header" width="100%" />
  <p><strong>Globaler LAN-Chat für Windows - klicki-bunti, schnell, ohne Server.</strong></p>
  <p>Walkür Technology · Strategus One · Silvan Fülle</p>

  <hr>
  <p align="center">
    <a href="https://github.com/PrivTEC/Walkuer_Lan_Chat/releases/tag/v1.0.0"
      style="color:#3fb950; text-decoration:none;">
      <strong style="font-size:1.3em; letter-spacing:0.5px;">
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓<br>
        ┃ ⬇ DOWNLOAD WINDOWS EXE v1.0.0 ┃<br>
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
      </strong>
    </a>
  </p>
  <p align="center">
    Single-file executable · No installer · No server · No cloud
  </p>
  <hr>

  <p>
    <a href="API.md">API</a> ·
    <a href="#features">Features</a> ·
    <a href="#funktionen-im-detail">Funktionen</a> ·
    <a href="#screenshots">Screenshots</a> ·
    <a href="#start">Start</a> ·
    <a href="LICENSE.md">Lizenz</a>
  </p>
</div>

Walkür LAN Chat ist ein kompaktes Windows-Tool für lokalen Netzwerk-Chat: ein globaler Raum im Intranet, automatische Discovery per UDP-Multicast, Dateitransfer per lokalem HTTP und ein dunkles Neon-UI im Walkür-Style. Kein Server, kein Cloud-Service, kein Internet nötig.

<div align="center">
  <img src="assets/feature-strip.svg" alt="Features" width="100%" />
</div>

## Features
- Globaler LAN-Chat (UDP Multicast, ein Raum für alle): **239.255.77.77:51337**
- Auto-Discovery + Presence (online/last seen, „tippt…“)
- Moderne Chat-Bubbles mit **Side-Tail** Richtung Avatar, Reply-Quote, Reactions, Edit/Undo, Pin-Leiste
- **WhatsApp-Style Link-Preview** im Composer: Titel, Beschreibung, Thumbnail, per X ausblendbar
- Link-Preview wird mitgesendet (inkl. Thumbnail-Hosting im LAN), im Chat als Preview-Card gerendert
- QR-Code für Links: **per Button togglen** (nicht dauerhaft im Weg)
- Datei-Transfer: Drag-and-Drop, Download per HTTP-URL, Fortschritt + Retry, Inline-Bildvorschau
- Chat-Hintergrund: **Aus / Farbe / Bild** + Opacity/Fade-Regler
- Themes: Standard, Pink Pupa, Midnight Blue, Mono Minimal
- Tray-Modus + Benachrichtigungen (optional Sound)
- Lokale API (optional, Token-geschützt) für Automationen
- Persistenz: History + Attachments + Avatare unter `%USERPROFILE%\.walkuer-lanchat\`

## Funktionen im Detail
- Chat & Formatierung: Markdown-Light mit klickbaren Links, sicheres Fallback, Textlimit **8 KB**.
- Interaktionen: Antworten (Quote), Reaktionen, Edit/Undo, Pin-Leiste mit Sprung zur Nachricht.
- Link-Preview:
  - Im Composer: Preview-Card erscheint automatisch bei URL im Text (mit X ausblendbar).
  - Beim Senden: Meta-Infos werden mitgeschickt; Thumbnails werden per integriertem HTTP-Server im LAN bereitgestellt.
  - Debug: `link_preview.log` unter `%USERPROFILE%\.walkuer-lanchat\logs\` (nur bei Partial/Fail).
- Presence: Online-Liste, letzter Online-Zeitpunkt, „tippt…“-Status.
- Dateien: Drag-and-Drop, lokaler HTTP-Download, Fortschritt + Retry, Inline-Bildvorschau.
- Offline Queue: Nachrichten werden bei Netzwerkverlust gepuffert und später gesendet.
- Persistenz: `history.jsonl`, `attachments/`, `avatars/`, `logs/` unter `%USERPROFILE%\.walkuer-lanchat\`.

## Warum es besonders ist
Kompakt, schnell, lokal. Für Teams, Studios, Werkstatt, Büro, LAN-Events. Keine Accounts, keine Serverkosten, keine Cloud-Abhängigkeit. Einfach starten und loschatten - mit Walkür-UI und ordentlich „Systemgefühl“.

## Screenshots
<div align="center">
  <img src="assets/Screenshot_1.png" alt="Hauptfenster" width="100%" />
  <img src="assets/Screenshot_2.png" alt="Einstellungen" width="100%" />
  <img src="assets/Screenshot_3.png" alt="Link-Preview & QR Toggle" width="100%" />
  <img src="assets/Screenshot_4.png" alt="Datei-Transfer & Vorschau" width="100%" />
</div>

## Start
### Dev
1. Python 3.11+ installieren
2. `run_dev.bat`

### Build (EXE)
1. `build_exe.bat`
2. Ergebnis: `dist\WalkuerLanChat.exe`

## Nutzung
1. App auf zwei PCs im gleichen LAN starten.
2. Windows-Firewall kann beim ersten Start fragen: Zugriff erlauben (Privates Netzwerk).
3. Chatten, Links posten (Preview im Composer), Dateien ziehen, fertig.

## Einstellungen
- Benutzername frei wählbar.
- Avatar wählen/entfernen (rund, mit Border).
- Theme-Auswahl: Standard, Pink Pupa, Midnight Blue, Mono Minimal.
- Sprache: Mehrsprachige UI (i18n JSON).
- Chat-Hintergrund: Aus / Farbe / Bild + Opacity/Fade.
- Sound bei neuen Nachrichten (an/aus).
- Tray-Popups (an/aus).
- Lokale API aktivieren: URL + Token anzeigen, Token neu generieren.
- Expert Mode: blendet erweiterte Optionen ein (falls aktiviert).

## Technik (Kurz)
- UI: **PySide6 (Qt Widgets)**, Themes per QSS, Splash-Screen per SVG.
- Netzwerk: UDP Multicast (Discovery + Chat), JSON-Messages, Rate-limited Presence.
- Files & Thumbnails: eingebetteter HTTP-Server (lokal), Caching in `attachments/`.
- Storage: `history.jsonl` + Attachments/Avatare/Logs im User-Home-Verzeichnis.
- i18n: Sprachdateien unter `src/lang/*.json`.

## API (lokal)
Details stehen in `API.md`. Kurzüberblick:
- `GET /api/v1/` Self-Description
- `GET /api/v1/status` Status + API-URL
- `GET /api/v1/peers` Online-Peers
- `GET /api/v1/messages?limit=50` History
- `POST /api/v1/send` Text senden
- `POST /api/v1/send/file` Datei senden (lokaler Pfad)
- `POST /api/v1/pin` / `POST /api/v1/unpin`
- `POST /api/v1/edit` / `POST /api/v1/undo`

**Quickstart (PowerShell)**
```powershell
$token = "<token>"
$base = "http://127.0.0.1:<port>/api/v1"
curl.exe "$base/status"
curl.exe -H "X-API-Token: $token" -H "Content-Type: application/json" `
  -d "{\"text\":\"test\"}" "$base/send"
```

## Suche & Keywords
LAN Chat, Windows LAN Chat, LAN Messenger, Intranet Chat, Local-first Chat, UDP Multicast, PySide6, Python 3.11, Walkür Technology, Strategus One, Silvan Fülle

## Attribution & Lizenz
Freie Nutzung für **nicht-kommerzielle Zwecke**. Kommerzielle Nutzung ist verboten.

Attribution ist Pflicht bei Nutzung/Weitergabe:
- Walkür Technology
- Strategus One
- Silvan Fülle
- https://walkuer.tech
- https://strategus.one

Details in `LICENSE.md`.
