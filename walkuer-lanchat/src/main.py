from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from config_store import ConfigStore
from net.message_store import HistoryStore
from net.multicast import LanChatNetwork
from net.api_service import ApiService
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
    apply_theme(app, store.config.theme)

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
    loaded_messages = history.load()

    for msg in loaded_messages:
        history_msg = dict(msg)
        history_msg["_from_history"] = True
        if history_msg.get("t") == "CHAT" and history_msg.get("subtype"):
            subtype = history_msg.get("subtype")
            if subtype == "REACT":
                window.apply_reaction(
                    history_msg.get("target_id", ""),
                    history_msg.get("emoji", ""),
                    history_msg.get("sender_id", ""),
                )
            elif subtype == "EDIT":
                window.apply_edit(history_msg.get("target_id", ""), history_msg.get("text", ""))
            elif subtype == "UNDO":
                window.apply_undo(history_msg.get("target_id", ""))
            elif subtype == "PIN":
                window.apply_pin(
                    history_msg.get("target_id", ""),
                    history_msg.get("preview", ""),
                    history_msg.get("name", ""),
                )
            elif subtype == "UNPIN":
                window.apply_unpin(history_msg.get("target_id", ""))
            continue
        window.add_message(
            history_msg,
            history_msg.get("sender_ip", ""),
            history_msg.get("sender_id") == store.config.sender_id,
        )

    from util.paths import attachment_cache_path

    for msg in loaded_messages:
        if msg.get("t") == "FILE" and msg.get("sender_id") == store.config.sender_id:
            file_id = msg.get("file_id")
            filename = msg.get("filename") or ""
            if file_id and filename:
                cache_path = attachment_cache_path(file_id, filename)
                if cache_path.exists():
                    network.register_cached_file(file_id, str(cache_path))

    def save_geometry() -> None:
        settings.setValue("geometry", window.saveGeometry())

    tray = None
    api_lock = threading.Lock()
    api_state = {"peers": [], "pinned": None}

    def update_api_peers(peers: list[dict]) -> None:
        with api_lock:
            api_state["peers"] = list(peers)

    def get_api_peers() -> list[dict]:
        with api_lock:
            return list(api_state["peers"])

    def update_api_pinned(pinned: dict | None) -> None:
        with api_lock:
            api_state["pinned"] = dict(pinned) if pinned else None

    def get_api_pinned() -> dict | None:
        with api_lock:
            pinned = api_state["pinned"]
            return dict(pinned) if pinned else None

    def get_api_history() -> list[dict]:
        return list(history.items)

    def get_api_self() -> dict:
        return {
            "sender_id": store.config.sender_id,
            "name": store.config.user_name,
            "avatar_sha256": store.config.avatar_sha256,
        }

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
        if msg.get("t") == "CHAT" and msg.get("subtype"):
            subtype = msg.get("subtype")
            if subtype == "REACT":
                window.apply_reaction(msg.get("target_id", ""), msg.get("emoji", ""), msg.get("sender_id", ""))
                return
            if subtype == "EDIT":
                window.apply_edit(msg.get("target_id", ""), msg.get("text", ""))
                history.append(msg)
                return
            if subtype == "UNDO":
                window.apply_undo(msg.get("target_id", ""))
                history.append(msg)
                return
            if subtype == "PIN":
                window.apply_pin(msg.get("target_id", ""), msg.get("preview", ""), msg.get("name", ""))
                history.append(msg)
                return
            if subtype == "UNPIN":
                window.apply_unpin(msg.get("target_id", ""))
                history.append(msg)
                return
        window.add_message(msg, sender_ip, False)
        history.append(msg)
        notify_if_needed(msg)

    def handle_send_text(payload: dict) -> None:
        text = payload.get("text") or ""
        meta = {k: v for k, v in payload.items() if k != "text"}
        link_preview = meta.get("link_preview")
        if isinstance(link_preview, dict):
            thumb_path = link_preview.pop("thumb_path", "") or ""
            thumb_file_id = link_preview.get("thumb_file_id") or ""
            if thumb_path and not thumb_file_id:
                import hashlib

                url_seed = link_preview.get("url") or ""
                digest = hashlib.sha1(url_seed.encode("utf-8")).hexdigest()
                thumb_file_id = f"lp_{digest[:12]}"
                link_preview["thumb_file_id"] = thumb_file_id
            if thumb_path and thumb_file_id:
                thumb_url = network.host_local_file(thumb_file_id, thumb_path)
                if thumb_url:
                    link_preview["thumb_url"] = thumb_url
        if meta:
            msg = network.send_chat_with_meta(text, meta)
        else:
            msg = network.send_chat(text)
        window.add_message(msg, "", True)
        history.append(dict(msg))

    def handle_edit_message(target_id: str, text: str) -> None:
        if not target_id:
            return
        msg = network.send_edit(target_id, text)
        history.append(dict(msg))

    def handle_undo_message(target_id: str) -> None:
        if not target_id:
            return
        msg = network.send_undo(target_id)
        history.append(dict(msg))

    def handle_pin_message(target_id: str, preview: str) -> None:
        if not target_id:
            return
        msg = network.send_pin(target_id, preview)
        history.append(dict(msg))

    def handle_unpin_message(target_id: str) -> None:
        if not target_id:
            return
        msg = network.send_unpin(target_id)
        history.append(dict(msg))

    def handle_send_files(paths: list[str]) -> None:
        for path in paths:
            try:
                from util.filehash import sha256_file
                import os
                import shutil
                import uuid
                from util.paths import attachment_cache_path

                file_id = str(uuid.uuid4())
                size = os.path.getsize(path)
                sha = sha256_file(path)
                filename = os.path.basename(path)
                cache_path = attachment_cache_path(file_id, filename)
                try:
                    if not cache_path.exists():
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, cache_path)
                    send_path = str(cache_path)
                except Exception:
                    send_path = path
                msg = network.send_file(file_id, send_path, filename, size, sha)
                window.add_message(msg, "", True)
                history.append(dict(msg))
            except Exception:
                window.show_status("Datei konnte nicht gesendet werden.")

    def show_settings(force: bool = False) -> None:
        dlg = SettingsDialog(store, api_url=_api_url(), force=force, parent=window)
        dlg.saved.connect(lambda: network.send_hello())
        dlg.saved.connect(lambda: apply_theme(app, store.config.theme))
        dlg.saved.connect(apply_api_settings)
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

    api_service = ApiService(
        token=store.config.api_token,
        enabled=store.config.api_enabled,
        send_text=window.send_text.emit,
        send_files=window.send_files.emit,
        send_edit=window.edit_message.emit,
        send_undo=window.undo_message.emit,
        send_pin=window.pin_message.emit,
        send_unpin=window.unpin_message.emit,
        get_peers=get_api_peers,
        get_history=get_api_history,
        get_pinned=get_api_pinned,
        get_queue_size=network.queue_size,
        get_self_info=get_api_self,
    )

    network.set_api_service(api_service)
    network.ensure_api(store.config.api_enabled)
    update_api_peers(network.peers_snapshot())
    update_api_pinned(window.get_pinned_message())

    def _api_url() -> str:
        port = network.api_port()
        if port <= 0:
            return "http://127.0.0.1:<port>/api/v1/"
        return f"http://127.0.0.1:{port}/api/v1/"

    def apply_api_settings() -> None:
        api_service.set_token(store.config.api_token)
        api_service.set_enabled(store.config.api_enabled)
        network.set_api_enabled(store.config.api_enabled)
        network.ensure_api(store.config.api_enabled)

    window.send_text.connect(handle_send_text)
    window.send_files.connect(handle_send_files)
    window.reaction_send.connect(lambda target_id, emoji: network.send_reaction(target_id, emoji))
    window.edit_message.connect(handle_edit_message)
    window.undo_message.connect(handle_undo_message)
    window.pin_message.connect(handle_pin_message)
    window.unpin_message.connect(handle_unpin_message)
    window.pinned_changed.connect(update_api_pinned)
    window.typing_changed.connect(network.set_typing)
    window.open_settings.connect(lambda: show_settings(False))
    window.open_about.connect(show_about)

    network.chat_received.connect(handle_incoming)
    network.file_received.connect(handle_incoming)
    network.online_count.connect(window.set_online_count)
    network.peers_updated.connect(window.set_peers)
    network.peers_updated.connect(update_api_peers)
    network.avatar_updated.connect(window.refresh_avatar)

    window.set_peers(network.peers_snapshot())

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
