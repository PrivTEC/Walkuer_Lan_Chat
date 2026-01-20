from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from config_store import ConfigStore
from net.message_store import HistoryStore
from net.multicast import LanChatNetwork
from theme import apply_theme
from tray import TrayManager
from ui_about import AboutDialog
from ui_main import MainWindow
from ui_settings import SettingsDialog
from util.images import app_icon
from util.paths import ensure_dirs, history_path, logs_dir
from util.sound import play_notification


def setup_logging() -> None:
    ensure_dirs()
    log_file = logs_dir() / "app.log"
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def main() -> int:
    setup_logging()
    store = ConfigStore()
    store.load()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)

    icon = app_icon()
    app.setWindowIcon(icon)

    settings = QSettings("WalkuerTechnology", "LanChat")

    window = MainWindow(store)
    window.setWindowIcon(icon)

    if settings.contains("geometry"):
        try:
            window.restoreGeometry(settings.value("geometry"))
        except Exception:
            pass

    network = LanChatNetwork(store)
    history = HistoryStore(history_path())

    for msg in history.load():
        window.add_message(msg, msg.get("sender_ip", ""), msg.get("sender_id") == store.config.sender_id)

    def save_geometry() -> None:
        settings.setValue("geometry", window.saveGeometry())

    tray = None

    def notify_if_needed(msg: dict) -> None:
        if not window.should_notify():
            return
        if store.config.tray_notifications and tray is not None:
            name = msg.get("name") or "Neue Nachricht"
            if msg.get("t") == "FILE":
                body = f"Datei: {msg.get('filename')}"
            else:
                body = (msg.get("text") or "")[:120]
            tray.show_message(name, body)
        play_notification(store.config.sound_enabled)

    def handle_incoming(msg: dict, sender_ip: str) -> None:
        msg = dict(msg)
        msg["sender_ip"] = sender_ip
        window.add_message(msg, sender_ip, False)
        history.append(msg)
        notify_if_needed(msg)

    def handle_send_text(text: str) -> None:
        msg = network.send_chat(text)
        window.add_message(msg, "", True)
        history.append(dict(msg))

    def handle_send_files(paths: list[str]) -> None:
        for path in paths:
            try:
                from util.filehash import sha256_file
                import os
                import uuid

                file_id = str(uuid.uuid4())
                size = os.path.getsize(path)
                sha = sha256_file(path)
                msg = network.send_file(file_id, path, os.path.basename(path), size, sha)
                window.add_message(msg, "", True)
                history.append(dict(msg))
            except Exception:
                window.show_status("Datei konnte nicht gesendet werden.")

    def show_settings(force: bool = False) -> None:
        dlg = SettingsDialog(store, force=force, parent=window)
        dlg.saved.connect(lambda: network.send_hello())
        dlg.exec()

    def show_about() -> None:
        dlg = AboutDialog(window)
        dlg.exec()

    def quit_app() -> None:
        save_geometry()
        network.shutdown()
        tray.hide()
        window.allow_close()
        app.quit()

    window.send_text.connect(handle_send_text)
    window.send_files.connect(handle_send_files)
    window.open_settings.connect(lambda: show_settings(False))
    window.open_about.connect(show_about)

    network.chat_received.connect(handle_incoming)
    network.file_received.connect(handle_incoming)
    network.online_count.connect(window.set_online_count)

    tray = TrayManager(icon, window, window.toggle_visibility, lambda: show_settings(False), show_about, quit_app)

    if not store.config.first_run_complete:
        show_settings(force=True)

    window.show()

    exit_code = app.exec()
    save_geometry()
    network.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
