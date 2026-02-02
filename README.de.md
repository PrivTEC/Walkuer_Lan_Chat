# Walkür LAN Chat

<div align="center">
  <img src="assets/hero.svg" alt="Walkür LAN Chat Header" width="100%" />
  <p><strong>Globaler LAN-Chat für Windows - klicky-bunt, schnell, ohne Server.</strong></p>
  <p>Walkür Technology · Strategus One · Silvan Fülle</p>

  <hr>
  <p align="center">
    ┏━━━━━━━━━━━━━━━━━┓<br>
    ⬇ <a href="https://github.com/PrivTEC/Walkuer_Lan_Chat/releases/tag/v1.0.0">
      <strong">
          WINDOWS-EXE v1.0.0 DOWNLOADEN<br>
      </strong>
    </a>
    ┗━━━━━━━━━━━━━━━━━┛
  </p>
  <p align="center">
    Einzeldatei-Executable · Kein Installer · Kein Server · Keine Cloud
  </p>
  <hr>

  <p>
    <a href="API.md">API</a> ·
    <a href="#features">Features</a> ·
    <a href="#functions-in-detail">Funktionen</a> ·
    <a href="#screenshots">Screenshots</a> ·
    <a href="#getting-started">Erste Schritte</a> ·
    <a href="LICENSE.md">Lizenz</a>
  </p>
</div>

Walkür LAN Chat ist ein kompaktes Windows-Tool für lokalen Netzwerk-Chat: ein globaler Raum in deinem Intranet, automatische Erkennung via UDP-Multicast, Dateiübertragung via lokalem HTTP und ein dunkles Neon-UI im Walkür-Stil. Kein Server, kein Cloud-Service, kein Internet erforderlich.

<div align="center">
  <img src="assets/feature-strip.svg" alt="Features" width="100%" />
</div>

## <a id="features"></a>Features
- Globaler LAN-Chat (UDP-Multicast, ein Raum für alle): **239.255.77.77:51337**
- Auto-Discovery + Presence (online/zuletzt gesehen, „tippt …“)
- Moderne Chat-Bubbles mit **Side-Tail** zum Avatar, Reply-Quote, Reactions, Edit/Undo, Pin-Bar
- **Link-Vorschau im WhatsApp-Stil** im Composer: Titel, Beschreibung, Thumbnail, per X ausblendbar
- Link-Vorschau wird mitgesendet (inkl. Thumbnail-Hosting im LAN) und als Preview-Card im Chat gerendert
- QR-Code für Links: **per Button toggelbar** (nicht ständig im Weg)
- Dateiübertragung: Drag-and-drop, Download via HTTP-URL, Fortschritt + Retry, Inline-Image-Preview
- Chat-Hintergrund: **Off / Farbe / Bild** + Opacity/Fade-Slider
- Themes: Standard, Pink Pupa, Midnight Blue, Mono Minimal
- Tray-Modus + Benachrichtigungen (optional mit Sound)
- Lokale API (optional, token-geschützt) für Automationen
- Persistenz: Verlauf + Attachments + Avatare unter `%USERPROFILE%\.walkuer-lanchat\`

## <a id="functions-in-detail"></a>Funktionen im Detail
- Chat & Formatierung: Markdown-light mit klickbaren Links, sicherer Fallback, Textlimit **8 KB**.
- Interaktionen: Reply (Quote), Reactions, Edit/Undo, Pin-Bar mit Jump zur Message.
- Link-Vorschau:
  - Im Composer: Preview-Card erscheint automatisch, sobald eine URL im Text steht (per X ausblendbar).
  - Beim Senden: Meta-Info wird übertragen; Thumbnails werden über den eingebauten HTTP-Server im LAN ausgeliefert.
  - Debug: `link_preview.log` unter `%USERPROFILE%\.walkuer-lanchat\logs\` (nur bei Partial/Fail).
- Presence: Online-Liste, Last-Seen-Timestamp, „tippt …“-Status.
- Dateien: Drag-and-drop, lokaler HTTP-Download, Fortschritt + Retry, Inline-Image-Preview.
- Offline-Queue: Nachrichten werden bei Netzverlust gepuffert und später gesendet.
- Persistenz: `history.jsonl`, `attachments/`, `avatars/`, `logs/` unter `%USERPROFILE%\.walkuer-lanchat\`.

## Warum es besonders ist
Kompakt, schnell, local-first. Für Teams, Studios, Werkstatt, Büro, LAN-Events. Keine Accounts, keine Serverkosten, keine Cloud-Abhängigkeit. Einfach starten und chatten - mit Walkür-UI und echtem „System-Feel“.

## <a id="screenshots"></a>Screenshots
<div align="center">
  <img src="assets/Screenshot_1.png" alt="Main window" width="100%" />
  <img src="assets/Screenshot_2.png" alt="Settings" width="100%" />
  <img src="assets/Screenshot_3.png" alt="Link preview & QR toggle" width="100%" />
  <img src="assets/Screenshot_4.png" alt="File transfer & preview" width="100%" />
</div>

## <a id="getting-started"></a>Erste Schritte
### Dev
1. Python 3.11+ installieren
2. `run_dev.bat`

### Build (EXE)
1. `build_exe.bat`
2. Output: `dist\WalkuerLanChat.exe`

## Nutzung
1. App auf zwei PCs im selben LAN starten.
2. Windows-Firewall kann beim ersten Start fragen: Zugriff erlauben (Privates Netzwerk).
3. Chatten, Links posten (Composer-Preview), Dateien ziehen - fertig.

## Einstellungen
- Username frei wählbar.
- Avatar wählen/entfernen (rund, mit Border).
- Theme-Auswahl: Standard, Pink Pupa, Midnight Blue, Mono Minimal.
- Sprache: mehrsprachiges UI (i18n JSON).
- Chat-Hintergrund: Off / Farbe / Bild + Opacity/Fade.
- Sound bei neuen Nachrichten (an/aus).
- Tray-Popups (an/aus).
- Lokale API aktivieren: URL + Token anzeigen, Token neu generieren.
- Expert Mode: erweitert erweiterte Optionen (wenn aktiviert).

## Tech (Kurz)
- UI: **PySide6 (Qt Widgets)**, Themes via QSS, Splash-Screen via SVG.
- Netzwerk: UDP-Multicast (Discovery + Chat), JSON-Messages, rate-limited Presence.
- Dateien & Thumbnails: eingebetteter HTTP-Server (lokal), Caching in `attachments/`.
- Storage: `history.jsonl` + attachments/avatars/logs im Home-Verzeichnis des Users.
- i18n: Sprachdateien unter `src/lang/*.json`.

## API (lokal)
Siehe `API.md` für Details. Quick-Overview:
- `GET /api/v1/` Self-Description
- `GET /api/v1/status` Status + API-URL
- `GET /api/v1/peers` Online-Peers
- `GET /api/v1/messages?limit=50` Verlauf
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
Kostenlos nutzbar für **nicht-kommerzielle Zwecke**. Kommerzielle Nutzung ist untersagt.

Attribution ist erforderlich bei Nutzung/Weiterverteilung:
- Walkür Technology
- Strategus One
- Silvan Fülle
- https://walkuer.tech
- https://strategus.one

Siehe `LICENSE.md` für Details.
