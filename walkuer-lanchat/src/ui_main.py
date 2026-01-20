from __future__ import annotations

import os
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import app_info
from config_store import ConfigStore
from net import protocol
from util.images import load_avatar_pixmap
from util.markdown_render import render_markdown
from util.paths import downloads_dir
from util.timefmt import fmt_time


class SendTextEdit(QTextEdit):
    send_requested = Signal()

    def keyPressEvent(self, event):  # noqa: N802 - Qt naming
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class DownloadWorker(QThread):
    progress = Signal(str, int)
    finished = Signal(str, str)
    failed = Signal(str, str)

    def __init__(self, url: str, dest_path: str, file_name: str) -> None:
        super().__init__()
        self._url = url
        self._dest_path = dest_path
        self._file_name = file_name

    def run(self) -> None:
        try:
            req = urllib.request.Request(self._url, headers={"User-Agent": "WalkuerLanChat"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                total = resp.headers.get("Content-Length")
                total_size = int(total) if total else 0
                Path(self._dest_path).parent.mkdir(parents=True, exist_ok=True)
                downloaded = 0
                with open(self._dest_path, "wb") as f:
                    while True:
                        chunk = resp.read(1024 * 128)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            pct = int((downloaded / total_size) * 100)
                            self.progress.emit(self._file_name, pct)
            self.finished.emit(self._file_name, self._dest_path)
        except Exception as exc:
            self.failed.emit(self._file_name, str(exc))


class ChatBubble(QFrame):
    download_requested = Signal(dict)

    def __init__(self, msg: dict, avatar_pixmap, is_self: bool, parent=None) -> None:
        super().__init__(parent)
        self.msg = msg
        self.setObjectName("chatBubbleSelf" if is_self else "chatBubble")

        layout = QHBoxLayout(self)
        layout.setSpacing(10)

        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(40, 40)
        self._avatar_label.setPixmap(avatar_pixmap)
        self._avatar_label.setScaledContents(True)

        body = QVBoxLayout()
        header = QHBoxLayout()

        name_label = QLabel(msg.get("name") or "?")
        name_label.setObjectName("nameLabel")
        time_label = QLabel(fmt_time(msg.get("ts") or 0))
        time_label.setObjectName("timeLabel")
        header.addWidget(name_label)
        header.addStretch(1)
        header.addWidget(time_label)

        body.addLayout(header)

        if msg.get("t") == "CHAT":
            text_widget = QLabel()
            text_widget.setTextFormat(Qt.RichText)
            text_widget.setOpenExternalLinks(True)
            text_widget.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
            text_widget.setWordWrap(True)
            text_widget.setStyleSheet("margin: 0px;")
            text_widget.setText(render_markdown(msg.get("text") or ""))
            body.addWidget(text_widget)
        else:
            file_box = QFrame()
            file_layout = QHBoxLayout(file_box)
            file_layout.setContentsMargins(6, 6, 6, 6)
            file_label = QLabel(f"{msg.get('filename')} ({_format_size(int(msg.get('size') or 0))})")
            file_label.setWordWrap(True)
            download_btn = QPushButton("Download")
            download_btn.clicked.connect(lambda: self.download_requested.emit(msg))
            file_layout.addWidget(file_label)
            file_layout.addStretch(1)
            file_layout.addWidget(download_btn)
            body.addWidget(file_box)

        layout.addWidget(self._avatar_label)
        layout.addLayout(body)
        layout.addStretch(1)

    def refresh_avatar(self, avatar_path: str, avatar_sha: str) -> None:
        pixmap = load_avatar_pixmap(
            avatar_path,
            self.msg.get("name") or "",
            avatar_sha,
            40,
        )
        self._avatar_label.setPixmap(pixmap)


class MainWindow(QMainWindow):
    send_text = Signal(str)
    send_files = Signal(list)
    open_settings = Signal()
    open_about = Signal()
    request_quit = Signal()

    def __init__(self, store: ConfigStore) -> None:
        super().__init__()
        self._store = store
        self._attachments: list[str] = []
        self._download_threads: list[DownloadWorker] = []
        self._allow_close = False

        self.setWindowTitle(app_info.APP_NAME)
        self.setMinimumSize(760, 560)
        self.setAcceptDrops(True)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setSpacing(10)

        topbar = QFrame()
        topbar.setObjectName("topBar")
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(8, 6, 8, 6)

        icon_label = QLabel("◆")
        icon_label.setStyleSheet("color: #39FF14; font-size: 12pt;")
        title_label = QLabel("LAN Chat")
        title_label.setStyleSheet("color: #E6FFE0; font-weight: 600;")

        settings_btn = QToolButton()
        settings_btn.setText("⚙")
        settings_btn.clicked.connect(self.open_settings)
        minimize_btn = QToolButton()
        minimize_btn.setText("_")
        minimize_btn.clicked.connect(self.showMinimized)
        close_btn = QToolButton()
        close_btn.setText("X")
        close_btn.clicked.connect(self._hide_to_tray)

        top_layout.addWidget(icon_label)
        top_layout.addWidget(title_label)
        top_layout.addStretch(1)
        top_layout.addWidget(settings_btn)
        top_layout.addWidget(minimize_btn)
        top_layout.addWidget(close_btn)

        header = QLabel("Walkür Technology")
        header.setObjectName("headerTitle")
        header.setAlignment(Qt.AlignCenter)
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(14)
        glow.setColor(Qt.green)
        glow.setOffset(0, 0)
        header.setGraphicsEffect(glow)

        self.online_label = QLabel("Online im LAN: 1")
        self.online_label.setAlignment(Qt.AlignCenter)
        self.online_label.setStyleSheet("color: #9BC49A;")

        self.chat_area = QScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch(1)
        self.chat_area.setWidget(self.chat_container)

        self.attachments_panel = QFrame()
        self.attachments_panel.setStyleSheet("background: #0F0F0F; border: 1px dashed #1E1E1E; border-radius: 6px;")
        self.attachments_layout = QVBoxLayout(self.attachments_panel)
        self.attachments_layout.setContentsMargins(8, 6, 8, 6)
        self.attachments_panel.hide()

        composer = QFrame()
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(0, 0, 0, 0)

        attach_btn = QPushButton("📎")
        attach_btn.setFixedWidth(40)
        attach_btn.clicked.connect(self._choose_files)

        self.text_input = SendTextEdit()
        self.text_input.setPlaceholderText("Nachricht schreiben...")
        self.text_input.setFixedHeight(80)
        self.text_input.setAcceptDrops(False)
        self.text_input.send_requested.connect(self._send_clicked)

        send_btn = QPushButton("Senden")
        send_btn.setFixedWidth(90)
        send_btn.clicked.connect(self._send_clicked)

        composer_layout.addWidget(attach_btn)
        composer_layout.addWidget(self.text_input, 1)
        composer_layout.addWidget(send_btn)

        root.addWidget(topbar)
        root.addWidget(header)
        root.addWidget(self.online_label)
        root.addWidget(self.chat_area, 1)
        root.addWidget(self.attachments_panel)
        root.addWidget(composer)

        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.status_label = QLabel("")
        self.status.addWidget(self.status_label)
        self.setStatusBar(self.status)

    def set_online_count(self, count: int) -> None:
        self.online_label.setText(f"Online im LAN: {count}")

    def add_message(self, msg: dict, sender_ip: str, is_self: bool) -> None:
        avatar = load_avatar_pixmap(
            self._store.config.avatar_path if is_self else "",
            msg.get("name") or "",
            msg.get("avatar_sha256") or "",
            40,
        )
        bubble = ChatBubble(msg, avatar, is_self)
        bubble.download_requested.connect(lambda m=msg: self._download_file(m, sender_ip))
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def refresh_avatar(self, sender_id: str, avatar_sha: str) -> None:
        for idx in range(self.chat_layout.count()):
            item = self.chat_layout.itemAt(idx)
            widget = item.widget()
            if isinstance(widget, ChatBubble):
                if widget.msg.get("sender_id") == sender_id and widget.msg.get("avatar_sha256") == avatar_sha:
                    widget.refresh_avatar("", avatar_sha)

    def show_status(self, text: str, timeout_ms: int = 3000) -> None:
        self.status_label.setText(text)
        if timeout_ms:
            QTimer.singleShot(timeout_ms, lambda: self.status_label.setText(""))

    def should_notify(self) -> bool:
        app = QApplication.instance()
        app_inactive = app is not None and app.applicationState() != Qt.ApplicationActive
        return (
            self.isHidden()
            or (self.windowState() & Qt.WindowMinimized)
            or not self.isActiveWindow()
            or app_inactive
        )

    def _send_clicked(self) -> None:
        text = self.text_input.toPlainText().strip()
        send_text = False
        if text:
            if len(text.encode("utf-8")) > protocol.MAX_TEXT_BYTES:
                self.show_status("Nachricht zu lang (max 8 KB).")
            else:
                send_text = True
        if send_text:
            self.send_text.emit(text)
            self.text_input.clear()

        if self._attachments:
            self.send_files.emit(list(self._attachments))
            self._attachments = []
            self._refresh_attachments()

    def _choose_files(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        files, _ = QFileDialog.getOpenFileNames(self, "Dateien auswählen")
        for path in files:
            self._add_attachment(path)

    def _add_attachment(self, path: str) -> None:
        if not path:
            return
        if not os.path.exists(path):
            return
        if path in self._attachments:
            return
        self._attachments.append(path)
        self._refresh_attachments()

    def _refresh_attachments(self) -> None:
        while self.attachments_layout.count():
            item = self.attachments_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._attachments:
            self.attachments_panel.hide()
            return
        for path in self._attachments:
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)
            try:
                size = os.path.getsize(path)
            except Exception:
                size = 0
            label = QLabel(f"Angehängt: {Path(path).name} ({_format_size(size)})")
            remove_btn = QToolButton()
            remove_btn.setText("X")
            remove_btn.clicked.connect(lambda _, p=path: self._remove_attachment(p))
            row_layout.addWidget(label)
            row_layout.addStretch(1)
            row_layout.addWidget(remove_btn)
            self.attachments_layout.addWidget(row)
        self.attachments_panel.show()

    def _remove_attachment(self, path: str) -> None:
        if path in self._attachments:
            self._attachments.remove(path)
            self._refresh_attachments()

    def _scroll_to_bottom(self) -> None:
        bar = self.chat_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _hide_to_tray(self) -> None:
        self.hide()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def allow_close(self) -> None:
        self._allow_close = True
        self.close()

    def closeEvent(self, event):  # noqa: N802 - Qt naming
        if self._allow_close:
            event.accept()
        else:
            self.hide()
            event.ignore()

    def dragEnterEvent(self, event):  # noqa: N802 - Qt naming
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: N802 - Qt naming
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    self._add_attachment(url.toLocalFile())
            event.acceptProposedAction()

    def _download_file(self, msg: dict, sender_ip: str) -> None:
        url = msg.get("url") or ""
        if not url:
            self.show_status("Download fehlgeschlagen: keine URL.")
            return
        parsed = urllib.parse.urlparse(url)
        if not parsed.netloc:
            url = f"http://{sender_ip}{parsed.path}"
        dest_dir = downloads_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = msg.get("filename") or "download.bin"
        dest_path = _unique_path(dest_dir, filename)

        worker = DownloadWorker(url, str(dest_path), filename)
        worker.progress.connect(lambda name, pct: self.status_label.setText(f"Lädt: {name} ({pct}%)"))
        worker.finished.connect(lambda name, p: self.status_label.setText(f"Fertig: {name}"))
        worker.failed.connect(lambda name, err: self.status_label.setText(f"Fehler: {name}"))
        worker.finished.connect(lambda *_: self._cleanup_worker())
        worker.failed.connect(lambda *_: self._cleanup_worker())
        self._download_threads.append(worker)
        worker.start()

    def _cleanup_worker(self) -> None:
        self._download_threads = [w for w in self._download_threads if w.isRunning()]


def _unique_path(folder: Path, filename: str) -> Path:
    base = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = folder / filename
    counter = 1
    while candidate.exists():
        candidate = folder / f"{base} ({counter}){suffix}"
        counter += 1
    return candidate


def _format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{int(value)} B"
