from __future__ import annotations

import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, Signal, QSize, QEvent, QPoint
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStatusBar,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QStyle,
)

import app_info
from config_store import ConfigStore
from net import protocol
from util.images import load_avatar_pixmap
from util.markdown_render import render_markdown
from util.paths import attachment_cache_path, downloads_dir
from util.timefmt import fmt_time, fmt_time_seconds


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


class ImageFetchWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, dest_path: str) -> None:
        super().__init__()
        self._url = url
        self._dest_path = dest_path

    def run(self) -> None:
        try:
            req = urllib.request.Request(self._url, headers={"User-Agent": "WalkuerLanChat"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            if not data:
                raise ValueError("empty image response")
            Path(self._dest_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self._dest_path, "wb") as f:
                f.write(data)
            self.finished.emit(self._dest_path)
        except Exception:
            self.failed.emit(self._dest_path)


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):  # noqa: N802 - Qt naming
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ImagePreviewDialog(QDialog):
    def __init__(self, image_path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bildvorschau")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        screen = QApplication.primaryScreen()
        max_w = 520
        max_h = 360
        if screen:
            avail = screen.availableGeometry()
            max_w = min(int(avail.width() * 0.55), 680)
            max_h = min(int(avail.height() * 0.5), 480)

        pixmap = QPixmap(image_path)
        label = ClickableLabel()
        label.setAlignment(Qt.AlignCenter)
        label.clicked.connect(self.accept)
        if not pixmap.isNull():
            scaled = pixmap.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(scaled)
            self.resize(scaled.width() + 20, scaled.height() + 20)
        else:
            label.setText("Vorschau nicht verfügbar")
            self.resize(max_w, max_h)

        layout.addWidget(label)
class UserListItem(QFrame):
    def __init__(
        self,
        sender_id: str,
        name: str,
        avatar_path: str,
        avatar_sha: str,
        typing: bool,
        last_seen: float,
        is_self: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.sender_id = sender_id
        self.avatar_sha = avatar_sha
        self._is_self = is_self
        self.setObjectName("userItemSelf" if is_self else "userItem")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self._avatar = QLabel()
        self._avatar.setFixedSize(28, 28)
        self._avatar.setScaledContents(True)

        labels = QVBoxLayout()
        labels.setSpacing(2)

        self._name_label = QLabel()
        self._name_label.setObjectName("userName")

        self._status_label = QLabel()
        self._status_label.setObjectName("userStatus")

        labels.addWidget(self._name_label)
        labels.addWidget(self._status_label)

        layout.addWidget(self._avatar)
        layout.addLayout(labels)
        layout.addStretch(1)

        self.update_display(name, avatar_path, avatar_sha, typing, last_seen)

    def update_display(
        self,
        name: str,
        avatar_path: str,
        avatar_sha: str,
        typing: bool,
        last_seen: float,
    ) -> None:
        self.avatar_sha = avatar_sha
        label = name or "User"
        if self._is_self:
            label = f"{label} (Du)"
        self._name_label.setText(label)

        pixmap = load_avatar_pixmap(avatar_path, name, avatar_sha, 28)
        self._avatar.setPixmap(pixmap)

        if typing:
            self._status_label.setText("tippt...")
            self._status_label.setObjectName("userStatusTyping")
        else:
            time_stamp = fmt_time_seconds(last_seen) if last_seen else ""
            suffix = f" · {time_stamp}" if time_stamp else ""
            self._status_label.setText(f"online{suffix}")
            self._status_label.setObjectName("userStatus")
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)

    def refresh_avatar(self, avatar_path: str, avatar_sha: str, name: str) -> None:
        self.avatar_sha = avatar_sha
        pixmap = load_avatar_pixmap(avatar_path, name, avatar_sha, 28)
        self._avatar.setPixmap(pixmap)


class ChatBubble(QFrame):
    reply_requested = Signal(dict)
    reaction_requested = Signal(dict, str)
    download_requested = Signal(dict)
    image_clicked = Signal(str)
    edit_requested = Signal(dict)
    undo_requested = Signal(dict)
    pin_requested = Signal(dict)
    unpin_requested = Signal(dict)

    def __init__(self, msg: dict, avatar_pixmap, is_self: bool, parent=None) -> None:
        super().__init__(parent)
        self.msg = msg
        self._reactions: dict[str, set[str]] = {}
        self._file_status: QLabel | None = None
        self._preview_label: ClickableLabel | None = None
        self._preview_path: str | None = None
        self._text_widget: QLabel | None = None
        self._time_label: QLabel | None = None
        self._is_self = is_self
        self._pinned = False
        self._progress: QProgressBar | None = None
        self._retry_btn: QPushButton | None = None
        self._download_btn: QPushButton | None = None

        self.setObjectName("chatBubbleSelf" if is_self else "chatBubble")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 10, 12, 10)

        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(40, 40)
        self._avatar_label.setPixmap(avatar_pixmap)
        self._avatar_label.setScaledContents(True)

        body = QVBoxLayout()
        body.setSpacing(6)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(msg.get("name") or "?")
        name_label.setObjectName("nameLabel")
        self._time_label = QLabel(fmt_time(msg.get("ts") or 0))
        self._time_label.setObjectName("timeLabel")

        reply_btn = QToolButton()
        reply_btn.setObjectName("replyButton")
        reply_btn.setText("↩")
        reply_btn.setToolTip("Antworten")
        reply_btn.clicked.connect(lambda: self.reply_requested.emit(self.msg))

        react_btn = QToolButton()
        react_btn.setObjectName("reactionButton")
        react_btn.setText("★")
        react_btn.setToolTip("Reagieren")
        react_btn.clicked.connect(self._open_reaction_menu)

        header.addWidget(name_label)
        header.addStretch(1)
        header.addWidget(reply_btn)
        header.addWidget(react_btn)
        header.addWidget(self._time_label)

        body.addLayout(header)

        reply_to = msg.get("reply_to")
        if reply_to:
            reply_box = QFrame()
            reply_box.setObjectName("replyBox")
            reply_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            reply_layout = QVBoxLayout(reply_box)
            reply_layout.setContentsMargins(8, 6, 8, 6)
            reply_layout.setSpacing(2)
            reply_name = QLabel(msg.get("reply_name") or "Antwort")
            reply_name.setObjectName("replyName")
            reply_preview = QLabel(_trim_text(msg.get("reply_preview") or ""))
            reply_preview.setObjectName("replyPreview")
            reply_preview.setWordWrap(True)
            reply_layout.addWidget(reply_name)
            reply_layout.addWidget(reply_preview)
            body.addWidget(reply_box)

        if msg.get("t") == "CHAT":
            self._text_widget = QLabel()
            self._text_widget.setObjectName("chatText")
            self._text_widget.setTextFormat(Qt.RichText)
            self._text_widget.setOpenExternalLinks(True)
            self._text_widget.setTextInteractionFlags(Qt.TextBrowserInteraction)
            self._text_widget.setWordWrap(True)
            self._text_widget.setStyleSheet("margin: 0px;")
            self._text_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self._set_text_content(msg.get("text") or "", bool(msg.get("deleted")))
            self._text_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            self._text_widget.customContextMenuRequested.connect(
                lambda pos: self._show_context_menu(self._text_widget.mapToGlobal(pos))
            )
            body.addWidget(self._text_widget)
        else:
            file_box = QFrame()
            file_box.setObjectName("fileCard")
            file_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            file_layout = QVBoxLayout(file_box)
            file_layout.setContentsMargins(10, 8, 10, 8)
            file_layout.setSpacing(6)

            self._preview_label = ClickableLabel()
            self._preview_label.setObjectName("imagePreview")
            self._preview_label.setFixedSize(240, 160)
            self._preview_label.setScaledContents(False)
            self._preview_label.hide()
            self._preview_label.clicked.connect(self._on_preview_clicked)

            file_label = QLabel(f"{msg.get('filename')} ({_format_size(int(msg.get('size') or 0))})")
            file_label.setObjectName("fileLabel")
            file_label.setWordWrap(True)
            file_label.setContextMenuPolicy(Qt.CustomContextMenu)
            file_label.customContextMenuRequested.connect(
                lambda pos: self._show_context_menu(file_label.mapToGlobal(pos))
            )

            self._progress = QProgressBar()
            self._progress.setObjectName("fileProgress")
            self._progress.setTextVisible(False)
            self._progress.setRange(0, 100)
            self._progress.hide()

            action_row = QHBoxLayout()
            self._file_status = QLabel("Bereit")
            self._file_status.setObjectName("fileStatus")
            self._download_btn = QPushButton("Download")
            self._download_btn.setObjectName("downloadButton")
            self._download_btn.clicked.connect(lambda: self.download_requested.emit(msg))
            self._retry_btn = QPushButton("Erneut")
            self._retry_btn.setObjectName("retryButton")
            self._retry_btn.clicked.connect(lambda: self.download_requested.emit(msg))
            self._retry_btn.hide()
            action_row.addWidget(self._file_status)
            action_row.addStretch(1)
            action_row.addWidget(self._retry_btn)
            action_row.addWidget(self._download_btn)

            file_layout.addWidget(self._preview_label)
            file_layout.addWidget(file_label)
            file_layout.addWidget(self._progress)
            file_layout.addLayout(action_row)
            body.addWidget(file_box)

        self._reaction_bar = QFrame()
        self._reaction_bar.setObjectName("reactionBar")
        self._reaction_layout = QHBoxLayout(self._reaction_bar)
        self._reaction_layout.setContentsMargins(0, 0, 0, 0)
        self._reaction_layout.setSpacing(6)
        self._reaction_bar.hide()
        body.addWidget(self._reaction_bar)

        layout.addWidget(self._avatar_label)
        layout.addLayout(body, 1)
        self._update_time_label()

    def contextMenuEvent(self, event):  # noqa: N802 - Qt naming
        self._show_context_menu(event.globalPos())

    def _show_context_menu(self, global_pos) -> None:
        menu = QMenu(self)
        copy_action = menu.addAction("Kopieren")
        edit_action = None
        undo_action = None
        pin_action = None
        if self._is_self and not self.msg.get("deleted") and self.msg.get("t") == "CHAT":
            edit_action = menu.addAction("Bearbeiten")
            undo_action = menu.addAction("Rückgängig")
        if self._pinned:
            pin_action = menu.addAction("Pin lösen")
        else:
            pin_action = menu.addAction("Anpinnen")
        action = menu.exec(global_pos)
        if action == copy_action:
            self._copy_to_clipboard()
        elif action == edit_action:
            self.edit_requested.emit(self.msg)
        elif action == undo_action:
            self.undo_requested.emit(self.msg)
        elif action == pin_action:
            if self._pinned:
                self.unpin_requested.emit(self.msg)
            else:
                self.pin_requested.emit(self.msg)

    def refresh_avatar(self, avatar_path: str, avatar_sha: str) -> None:
        pixmap = load_avatar_pixmap(
            avatar_path,
            self.msg.get("name") or "",
            avatar_sha,
            40,
        )
        self._avatar_label.setPixmap(pixmap)

    def set_download_status(self, text: str) -> None:
        if self._file_status is not None:
            self._file_status.setText(text)
        if self._download_btn is not None:
            self._download_btn.setEnabled(text != "Lädt...")
        if self._retry_btn is not None:
            self._retry_btn.setVisible(text == "Fehler")
        if self._progress is not None:
            if text.startswith("Lädt"):
                self._progress.show()
            else:
                self._progress.hide()

    def set_download_progress(self, pct: int) -> None:
        if self._progress is not None:
            self._progress.setValue(pct)
            if pct >= 100:
                self._progress.hide()
            else:
                self._progress.show()
        if self._file_status is not None:
            self._file_status.setText(f"Lädt... {pct}%")
        if self._download_btn is not None:
            self._download_btn.setEnabled(False)
        if self._retry_btn is not None:
            self._retry_btn.hide()

    def set_image_preview(self, path: str) -> None:
        if not self._preview_label:
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        self._preview_path = path
        scaled = pixmap.scaled(
            self._preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)
        self._preview_label.show()

    def set_pinned(self, pinned: bool) -> None:
        self._pinned = pinned

    def apply_edit(self, text: str) -> None:
        if not self._text_widget:
            return
        self.msg["text"] = text
        self.msg["edited"] = True
        self._set_text_content(text, False)
        self._update_time_label()

    def apply_undo(self) -> None:
        if not self._text_widget:
            return
        self.msg["deleted"] = True
        self._set_text_content("", True)
        self._update_time_label()

    def _set_text_content(self, text: str, deleted: bool) -> None:
        if not self._text_widget:
            return
        if deleted:
            self._text_widget.setText("<i>Nachricht gelöscht</i>")
            self._text_widget.setObjectName("chatTextMuted")
        else:
            self._text_widget.setText(render_markdown(text))
            self._text_widget.setObjectName("chatText")
        self._text_widget.style().unpolish(self._text_widget)
        self._text_widget.style().polish(self._text_widget)

    def _update_time_label(self) -> None:
        if not self._time_label:
            return
        label = fmt_time(self.msg.get("ts") or 0)
        if self.msg.get("edited"):
            label = f"{label} · bearbeitet"
        self._time_label.setText(label)

    def _copy_to_clipboard(self) -> None:
        text = ""
        if self.msg.get("t") == "CHAT":
            if self.msg.get("deleted"):
                text = ""
            else:
                text = self.msg.get("text") or ""
        else:
            filename = self.msg.get("filename") or ""
            url = self.msg.get("url") or ""
            text = f"{filename} {url}".strip()
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def _on_preview_clicked(self) -> None:
        if self._preview_path:
            self.image_clicked.emit(self._preview_path)

    def matches_filter(self, query: str) -> bool:
        q = (query or "").strip().lower()
        if not q:
            return True
        fields = [
            self.msg.get("name") or "",
            self.msg.get("text") or "",
            self.msg.get("filename") or "",
            self.msg.get("reply_preview") or "",
        ]
        return any(q in str(field).lower() for field in fields)

    def apply_reaction(self, emoji: str, sender_id: str) -> None:
        if not emoji or not sender_id:
            return
        senders = self._reactions.setdefault(emoji, set())
        if sender_id in senders:
            return
        senders.add(sender_id)
        self._render_reactions()

    def _render_reactions(self) -> None:
        while self._reaction_layout.count():
            item = self._reaction_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._reactions:
            self._reaction_bar.hide()
            return
        for emoji, senders in self._reactions.items():
            chip = QFrame()
            chip.setObjectName("reactionChip")
            chip_layout = QHBoxLayout(chip)
            chip_layout.setContentsMargins(6, 2, 6, 2)
            chip_layout.setSpacing(4)
            label = QLabel(f"{emoji} {len(senders)}")
            label.setObjectName("reactionText")
            chip_layout.addWidget(label)
            self._reaction_layout.addWidget(chip)
        self._reaction_layout.addStretch(1)
        self._reaction_bar.show()

    def _open_reaction_menu(self) -> None:
        menu = QMenu(self)
        for emoji in ["👍", "⚡", "🔥", "💬", "✅"]:
            action = menu.addAction(emoji)
            action.triggered.connect(lambda _, e=emoji: self.reaction_requested.emit(self.msg, e))
        menu.exec(self.mapToGlobal(self.rect().bottomRight()))


class MainWindow(QMainWindow):
    send_text = Signal(dict)
    send_files = Signal(list)
    reaction_send = Signal(str, str)
    edit_message = Signal(str, str)
    undo_message = Signal(str)
    pin_message = Signal(str, str)
    unpin_message = Signal(str)
    pinned_changed = Signal(object)
    typing_changed = Signal(bool)
    open_settings = Signal()
    open_about = Signal()
    request_quit = Signal()

    def __init__(self, store: ConfigStore) -> None:
        super().__init__()
        self._store = store
        self._attachments: list[str] = []
        self._download_threads: list[DownloadWorker] = []
        self._image_fetch_threads: list[ImageFetchWorker] = []
        self._allow_close = False
        self._message_bubbles: dict[str, ChatBubble] = {}
        self._file_bubbles: dict[str, ChatBubble] = {}
        self._reply_target: dict[str, Any] | None = None
        self._edit_target: dict[str, Any] | None = None
        self._pinned_message: dict[str, Any] | None = None
        self._typing_state = False
        self._typing_timer = QTimer(self)
        self._typing_timer.setSingleShot(True)
        self._typing_timer.timeout.connect(lambda: self._set_typing(False))
        self._peers: list[dict[str, Any]] = []
        self._user_items: dict[str, UserListItem] = {}
        self._stick_to_bottom = True
        self._drag_active = False
        self._drag_offset = QPoint()

        self.setWindowTitle(app_info.APP_NAME)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setMinimumSize(860, 600)
        self.setAcceptDrops(True)

        central = QWidget()
        central.setObjectName("appRoot")
        root = QVBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(12, 10, 12, 12)

        topbar = QFrame()
        topbar.setObjectName("topBar")
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(10, 6, 10, 6)
        top_layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setFixedSize(18, 18)
        app_icon = QApplication.windowIcon()
        if not app_icon.isNull():
            icon_label.setPixmap(app_icon.pixmap(18, 18))
        else:
            icon_label.setText("W")

        title_label = QLabel("LAN Chat")
        title_label.setObjectName("appTitle")

        style = self.style()

        settings_btn = QToolButton()
        settings_btn.setText("⚙")
        settings_btn.setToolTip("Einstellungen")
        settings_btn.clicked.connect(self.open_settings)
        minimize_btn = QToolButton()
        minimize_btn.setIcon(style.standardIcon(QStyle.SP_TitleBarMinButton))
        minimize_btn.setIconSize(QSize(12, 12))
        minimize_btn.setToolTip("Minimieren")
        minimize_btn.clicked.connect(self.showMinimized)
        close_btn = QToolButton()
        close_btn.setIcon(style.standardIcon(QStyle.SP_TitleBarCloseButton))
        close_btn.setIconSize(QSize(12, 12))
        close_btn.setToolTip("Schließen")
        close_btn.clicked.connect(self._hide_to_tray)

        top_layout.addWidget(icon_label)
        top_layout.addWidget(title_label)
        top_layout.addStretch(1)
        top_layout.addWidget(settings_btn)
        top_layout.addWidget(minimize_btn)
        top_layout.addWidget(close_btn)

        self._drag_widgets = {topbar, title_label, icon_label}
        for widget in self._drag_widgets:
            widget.installEventFilter(self)

        header = QLabel("Walkür Technology")
        header.setObjectName("headerTitle")
        header.setAlignment(Qt.AlignCenter)
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(14)
        glow.setColor(Qt.green)
        glow.setOffset(0, 0)
        header.setGraphicsEffect(glow)

        meta_bar = QFrame()
        meta_bar.setObjectName("metaBar")
        meta_layout = QHBoxLayout(meta_bar)
        meta_layout.setContentsMargins(4, 0, 4, 0)
        meta_layout.setSpacing(8)

        self.online_label = QLabel("Online im LAN: 1")
        self.online_label.setObjectName("onlineLabel")
        self.online_label.setAlignment(Qt.AlignLeft)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Suche im Chat...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_filter)

        meta_layout.addWidget(self.online_label)
        meta_layout.addStretch(1)
        meta_layout.addWidget(self.search_input)

        content_frame = QFrame()
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self.user_panel = QFrame()
        self.user_panel.setObjectName("userListPanel")
        self.user_panel.setFixedWidth(220)
        user_layout = QVBoxLayout(self.user_panel)
        user_layout.setContentsMargins(10, 10, 10, 10)
        user_layout.setSpacing(8)

        user_title = QLabel("Online")
        user_title.setObjectName("userListTitle")

        self.user_list_area = QScrollArea()
        self.user_list_area.setWidgetResizable(True)
        self.user_list_area.setFrameShape(QFrame.NoFrame)

        self.user_list_container = QWidget()
        self.user_list_layout = QVBoxLayout(self.user_list_container)
        self.user_list_layout.setContentsMargins(0, 0, 0, 0)
        self.user_list_layout.setSpacing(6)
        self.user_list_layout.addStretch(1)
        self.user_list_area.setWidget(self.user_list_container)

        user_layout.addWidget(user_title)
        user_layout.addWidget(self.user_list_area, 1)

        chat_panel = QFrame()
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(8)

        self.chat_area = QScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_area.setFrameShape(QFrame.NoFrame)

        self.chat_container = QWidget()
        self.chat_container.setObjectName("chatCanvas")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setSpacing(10)
        self.chat_layout.setContentsMargins(12, 12, 12, 12)
        self.chat_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.chat_area.setWidget(self.chat_container)
        scroll_bar = self.chat_area.verticalScrollBar()
        scroll_bar.valueChanged.connect(self._on_scroll_changed)
        scroll_bar.rangeChanged.connect(self._on_scroll_range_changed)

        self.pinned_bar = QFrame()
        self.pinned_bar.setObjectName("pinnedBar")
        pinned_layout = QHBoxLayout(self.pinned_bar)
        pinned_layout.setContentsMargins(10, 6, 10, 6)
        pinned_layout.setSpacing(6)
        self.pinned_label = ClickableLabel()
        self.pinned_label.setObjectName("pinnedLabel")
        self.pinned_label.setCursor(Qt.PointingHandCursor)
        self.pinned_label.clicked.connect(self._scroll_to_pinned)
        self.pinned_clear_btn = QToolButton()
        self.pinned_clear_btn.setObjectName("pinnedClear")
        self.pinned_clear_btn.setText("X")
        self.pinned_clear_btn.clicked.connect(self._clear_pin)
        pinned_layout.addWidget(self.pinned_label)
        pinned_layout.addStretch(1)
        pinned_layout.addWidget(self.pinned_clear_btn)
        self.pinned_bar.hide()

        self.attachments_panel = QFrame()
        self.attachments_panel.setObjectName("attachmentsPanel")
        self.attachments_layout = QVBoxLayout(self.attachments_panel)
        self.attachments_layout.setContentsMargins(8, 6, 8, 6)
        self.attachments_panel.hide()

        self.edit_bar = QFrame()
        self.edit_bar.setObjectName("editBar")
        edit_layout = QHBoxLayout(self.edit_bar)
        edit_layout.setContentsMargins(8, 6, 8, 6)
        edit_layout.setSpacing(6)
        self.edit_label = QLabel("")
        self.edit_label.setObjectName("editLabel")
        self.edit_clear_btn = QToolButton()
        self.edit_clear_btn.setObjectName("editClear")
        self.edit_clear_btn.setText("X")
        self.edit_clear_btn.clicked.connect(self._clear_edit)
        edit_layout.addWidget(self.edit_label)
        edit_layout.addStretch(1)
        edit_layout.addWidget(self.edit_clear_btn)
        self.edit_bar.hide()

        self.reply_bar = QFrame()
        self.reply_bar.setObjectName("replyBar")
        reply_layout = QHBoxLayout(self.reply_bar)
        reply_layout.setContentsMargins(8, 6, 8, 6)
        reply_layout.setSpacing(6)
        self.reply_label = QLabel("")
        self.reply_label.setObjectName("replyLabel")
        self.reply_clear_btn = QToolButton()
        self.reply_clear_btn.setObjectName("replyClear")
        self.reply_clear_btn.setText("X")
        self.reply_clear_btn.clicked.connect(self._clear_reply)
        reply_layout.addWidget(self.reply_label)
        reply_layout.addStretch(1)
        reply_layout.addWidget(self.reply_clear_btn)
        self.reply_bar.hide()

        self.emoji_bar = QFrame()
        self.emoji_bar.setObjectName("emojiBar")
        emoji_layout = QHBoxLayout(self.emoji_bar)
        emoji_layout.setContentsMargins(8, 4, 8, 4)
        emoji_layout.setSpacing(6)
        for emoji in ["😀", "😂", "😉", "😍", "👍", "🔥", "⚡", "✅"]:
            btn = QToolButton()
            btn.setObjectName("emojiButton")
            btn.setText(emoji)
            btn.setToolTip(emoji)
            btn.clicked.connect(lambda _, e=emoji: self._insert_emoji(e))
            emoji_layout.addWidget(btn)
        emoji_layout.addStretch(1)

        composer = QFrame()
        composer.setObjectName("composerBar")
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(8, 8, 8, 8)
        composer_layout.setSpacing(8)

        attach_btn = QPushButton()
        attach_btn.setObjectName("iconButton")
        attach_btn.setText("📎")
        attach_btn.setToolTip("Datei anhängen")
        attach_btn.setFixedSize(40, 40)
        attach_btn.clicked.connect(self._choose_files)

        self.text_input = SendTextEdit()
        self.text_input.setPlaceholderText("Nachricht schreiben...")
        self.text_input.setFixedHeight(80)
        self.text_input.setAcceptDrops(False)
        self.text_input.send_requested.connect(self._send_clicked)
        self.text_input.textChanged.connect(self._on_text_changed)

        send_btn = QPushButton("Senden")
        send_btn.setObjectName("primaryButton")
        send_btn.setFixedWidth(110)
        send_btn.clicked.connect(self._send_clicked)

        composer_layout.addWidget(attach_btn)
        composer_layout.addWidget(self.text_input, 1)
        composer_layout.addWidget(send_btn)

        chat_layout.addWidget(self.pinned_bar)
        chat_layout.addWidget(self.chat_area, 1)
        chat_layout.addWidget(self.attachments_panel)
        chat_layout.addWidget(self.edit_bar)
        chat_layout.addWidget(self.reply_bar)
        chat_layout.addWidget(self.emoji_bar)
        chat_layout.addWidget(composer)

        content_layout.addWidget(self.user_panel)
        content_layout.addWidget(chat_panel, 1)

        root.addWidget(topbar)
        root.addWidget(header)
        root.addWidget(meta_bar)
        root.addWidget(content_frame, 1)

        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.status_label = QLabel("")
        self.status.addWidget(self.status_label)
        self.setStatusBar(self.status)

        self._render_user_list()

    def resizeEvent(self, event):  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self._update_bubble_widths()

    def _update_bubble_widths(self) -> None:
        max_width = max(340, int(self.chat_area.viewport().width() * 0.78))
        min_width = max(220, int(self.chat_area.viewport().width() * 0.34))
        if min_width > max_width:
            min_width = max_width
        for bubble in self._message_bubbles.values():
            bubble.setMaximumWidth(max_width)
            bubble.setMinimumWidth(min_width)

    def set_online_count(self, count: int) -> None:
        self.online_label.setText(f"Online im LAN: {count}")

    def set_peers(self, peers: list[dict[str, Any]]) -> None:
        self._peers = peers
        other_peers = [p for p in peers if p.get("sender_id") != self._store.config.sender_id]
        self.online_label.setText(f"Online im LAN: {len(other_peers) + 1}")
        self._render_user_list()

    def _render_user_list(self) -> None:
        while self.user_list_layout.count():
            item = self.user_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._user_items = {}

        self_item = UserListItem(
            self._store.config.sender_id,
            self._store.config.user_name,
            self._store.config.avatar_path,
            self._store.config.avatar_sha256,
            self._typing_state,
            time.time(),
            True,
        )
        self._user_items[self._store.config.sender_id] = self_item
        self.user_list_layout.addWidget(self_item)

        peers = sorted(
            [p for p in self._peers if p.get("sender_id") != self._store.config.sender_id],
            key=lambda p: (p.get("name") or "").lower(),
        )
        for peer in peers:
            item = UserListItem(
                peer.get("sender_id") or "",
                peer.get("name") or "",
                "",
                peer.get("avatar_sha256") or "",
                bool(peer.get("typing", False)),
                float(peer.get("last_seen") or 0),
                False,
            )
            self._user_items[item.sender_id] = item
            self.user_list_layout.addWidget(item)

        self.user_list_layout.addStretch(1)

    def add_message(self, msg: dict, sender_ip: str, is_self: bool) -> None:
        avatar = load_avatar_pixmap(
            self._store.config.avatar_path if is_self else "",
            msg.get("name") or "",
            msg.get("avatar_sha256") or "",
            40,
        )
        bubble = ChatBubble(msg, avatar, is_self)
        bubble.download_requested.connect(lambda m=msg: self._download_file(m, sender_ip))
        bubble.reply_requested.connect(lambda m=msg: self._set_reply(m))
        bubble.reaction_requested.connect(lambda m, e: self._send_reaction(m, e))
        bubble.edit_requested.connect(lambda m=msg: self._set_edit(m))
        bubble.undo_requested.connect(lambda m=msg: self._send_undo(m))
        bubble.pin_requested.connect(lambda m=msg: self._pin_message(m))
        bubble.unpin_requested.connect(lambda m=msg: self._unpin_message(m))
        bubble.image_clicked.connect(self._open_image_preview)

        msg_id = msg.get("message_id")
        if msg_id:
            self._message_bubbles[msg_id] = bubble
        file_id = msg.get("file_id")
        if file_id:
            self._file_bubbles[file_id] = bubble

        alignment = Qt.AlignRight if is_self else Qt.AlignLeft
        self.chat_layout.addWidget(bubble, alignment=alignment)
        if self._pinned_message and msg.get("message_id") == self._pinned_message.get("target_id"):
            bubble.set_pinned(True)
        if msg.get("t") == "FILE":
            self._ensure_image_preview(msg, bubble)
        self._update_bubble_widths()
        self._apply_filter()
        self._scroll_to_bottom(force=is_self)

    def apply_reaction(self, target_id: str, emoji: str, sender_id: str) -> None:
        bubble = self._message_bubbles.get(target_id)
        if bubble:
            bubble.apply_reaction(emoji, sender_id)

    def apply_edit(self, target_id: str, text: str) -> bool:
        bubble = self._message_bubbles.get(target_id)
        if not bubble:
            return False
        bubble.apply_edit(text)
        return True

    def apply_undo(self, target_id: str) -> bool:
        bubble = self._message_bubbles.get(target_id)
        if not bubble:
            return False
        bubble.apply_undo()
        if self._pinned_message and self._pinned_message.get("target_id") == target_id:
            self.apply_unpin(target_id)
        return True

    def apply_pin(self, target_id: str, preview: str, name: str) -> None:
        self._pinned_message = {"target_id": target_id, "preview": preview, "name": name}
        label = f"\U0001F4CC Angepinnt: {preview}"
        if name:
            label = f"\U0001F4CC {name}: {preview}"
        self.pinned_label.setText(label)
        self.pinned_bar.show()
        for bubble in self._message_bubbles.values():
            bubble.set_pinned(bubble.msg.get("message_id") == target_id)
        self.pinned_changed.emit(dict(self._pinned_message))

    def apply_unpin(self, target_id: str) -> None:
        if self._pinned_message and self._pinned_message.get("target_id") == target_id:
            self._pinned_message = None
        self.pinned_bar.hide()
        for bubble in self._message_bubbles.values():
            bubble.set_pinned(False)
        self.pinned_changed.emit(None)

    def get_pinned_message(self) -> dict[str, Any] | None:
        if not self._pinned_message:
            return None
        return dict(self._pinned_message)

    def refresh_avatar(self, sender_id: str, avatar_sha: str) -> None:
        for idx in range(self.chat_layout.count()):
            item = self.chat_layout.itemAt(idx)
            widget = item.widget()
            if isinstance(widget, ChatBubble):
                if widget.msg.get("sender_id") == sender_id and widget.msg.get("avatar_sha256") == avatar_sha:
                    widget.refresh_avatar("", avatar_sha)
        item = self._user_items.get(sender_id)
        if item:
            name = item._name_label.text().replace(" (Du)", "")
            item.refresh_avatar("", avatar_sha, name)

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

    def _on_text_changed(self) -> None:
        text = self.text_input.toPlainText().strip()
        if text:
            if not self._typing_state:
                self._set_typing(True)
            self._typing_timer.start(1500)
        else:
            self._typing_timer.stop()
            self._set_typing(False)

    def _set_typing(self, state: bool) -> None:
        if state == self._typing_state:
            return
        self._typing_state = state
        self.typing_changed.emit(state)
        self._render_user_list()

    def _set_reply(self, msg: dict) -> None:
        self._clear_edit()
        self._reply_target = msg
        preview = msg.get("text") or msg.get("filename") or ""
        preview = _trim_text(preview)
        name = msg.get("name") or "?"
        self.reply_label.setText(f"Antwort an {name}: {preview}")
        self.reply_bar.show()

    def _clear_reply(self) -> None:
        self._reply_target = None
        self.reply_bar.hide()

    def _set_edit(self, msg: dict) -> None:
        if msg.get("t") != "CHAT" or msg.get("deleted"):
            return
        self._clear_reply()
        self._edit_target = msg
        preview = _trim_text(msg.get("text") or "")
        self.edit_label.setText(f"Bearbeiten: {preview}")
        self.edit_bar.show()
        self.text_input.setPlainText(msg.get("text") or "")
        self.text_input.setFocus()

    def _clear_edit(self) -> None:
        self._edit_target = None
        self.edit_bar.hide()

    def _send_undo(self, msg: dict) -> None:
        target_id = msg.get("message_id") or ""
        if not target_id:
            return
        self.apply_undo(target_id)
        self.undo_message.emit(target_id)

    def _pin_message(self, msg: dict) -> None:
        target_id = msg.get("message_id") or ""
        if not target_id:
            return
        preview = _trim_text(msg.get("text") or msg.get("filename") or "")
        name = msg.get("name") or ""
        self.apply_pin(target_id, preview, name)
        self.pin_message.emit(target_id, preview)

    def _unpin_message(self, msg: dict) -> None:
        target_id = msg.get("message_id") or ""
        if not target_id:
            return
        self.apply_unpin(target_id)
        self.unpin_message.emit(target_id)

    def _clear_pin(self) -> None:
        if not self._pinned_message:
            return
        target_id = self._pinned_message.get("target_id") or ""
        if not target_id:
            return
        self.apply_unpin(target_id)
        self.unpin_message.emit(target_id)

    def _send_reaction(self, msg: dict, emoji: str) -> None:
        target_id = msg.get("message_id")
        if not target_id:
            return
        self.apply_reaction(target_id, emoji, self._store.config.sender_id)
        self.reaction_send.emit(target_id, emoji)

    def _insert_emoji(self, emoji: str) -> None:
        cursor = self.text_input.textCursor()
        cursor.insertText(emoji)
        self.text_input.setTextCursor(cursor)
        self.text_input.setFocus()

    def _send_clicked(self) -> None:
        text = self.text_input.toPlainText().strip()
        if self._edit_target:
            target_id = self._edit_target.get("message_id") or ""
            if text and len(text.encode("utf-8")) > protocol.MAX_TEXT_BYTES:
                self.show_status("Bearbeiten: Nachricht zu lang (max 8 KB).")
                return
            if target_id and text:
                self.apply_edit(target_id, text)
                self.edit_message.emit(target_id, text)
            else:
                self.show_status("Bearbeiten: Text fehlt.")
            self.text_input.clear()
            self._clear_edit()
            self._set_typing(False)
            return
        send_text = False
        if text:
            if len(text.encode("utf-8")) > protocol.MAX_TEXT_BYTES:
                self.show_status("Nachricht zu lang (max 8 KB).")
            else:
                send_text = True
        if send_text:
            payload: dict[str, Any] = {"text": text}
            if self._reply_target:
                payload.update(
                    {
                        "reply_to": self._reply_target.get("message_id"),
                        "reply_name": self._reply_target.get("name") or "",
                        "reply_preview": _trim_text(
                            self._reply_target.get("text")
                            or self._reply_target.get("filename")
                            or ""
                        ),
                        "reply_type": self._reply_target.get("t") or "",
                    }
                )
            self.send_text.emit(payload)
            self.text_input.clear()
            self._clear_reply()
            self._set_typing(False)

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

    def _apply_filter(self) -> None:
        query = self.search_input.text()
        for idx in range(self.chat_layout.count()):
            item = self.chat_layout.itemAt(idx)
            widget = item.widget()
            if isinstance(widget, ChatBubble):
                widget.setVisible(widget.matches_filter(query))

    def _scroll_to_bottom(self, force: bool = False) -> None:
        if not force and not self._stick_to_bottom:
            return
        bar = self.chat_area.verticalScrollBar()
        QTimer.singleShot(0, lambda: bar.setValue(bar.maximum()))

    def _scroll_to_pinned(self) -> None:
        if not self._pinned_message:
            return
        target_id = self._pinned_message.get("target_id") or ""
        if not target_id:
            return
        if not self._scroll_to_message(target_id):
            self.show_status("Angepinnte Nachricht nicht gefunden.")

    def _scroll_to_message(self, message_id: str) -> bool:
        bubble = self._message_bubbles.get(message_id)
        if not bubble:
            return False
        self.chat_area.ensureWidgetVisible(bubble, 0, 20)
        self._flash_bubble(bubble)
        return True

    def _flash_bubble(self, bubble: ChatBubble) -> None:
        bubble.setProperty("flash", True)
        bubble.style().unpolish(bubble)
        bubble.style().polish(bubble)

        def clear_flash() -> None:
            bubble.setProperty("flash", False)
            bubble.style().unpolish(bubble)
            bubble.style().polish(bubble)

        QTimer.singleShot(900, clear_flash)

    def _on_scroll_changed(self, value: int) -> None:
        bar = self.chat_area.verticalScrollBar()
        self._stick_to_bottom = value >= (bar.maximum() - 24)

    def _on_scroll_range_changed(self, _min: int, _max: int) -> None:
        if self._stick_to_bottom:
            self._scroll_to_bottom(force=True)

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

    def eventFilter(self, obj, event):  # noqa: N802 - Qt naming
        if obj in getattr(self, "_drag_widgets", set()):
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_active = True
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            if event.type() == QEvent.MouseMove and self._drag_active:
                if self.windowState() & Qt.WindowMaximized:
                    return True
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                return True
            if event.type() == QEvent.MouseButtonRelease and self._drag_active:
                self._drag_active = False
                return True
        return super().eventFilter(obj, event)

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
        filename = msg.get("filename") or "download.bin"
        file_id = msg.get("file_id") or ""
        if file_id:
            dest_path = attachment_cache_path(file_id, filename)
        else:
            dest_dir = downloads_dir()
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = _unique_path(dest_dir, filename)

        if dest_path.exists():
            bubble = self._file_bubbles.get(file_id) if file_id else None
            if bubble:
                bubble.set_download_status("Bereits vorhanden")
                if _is_image_file(filename):
                    bubble.set_image_preview(str(dest_path))
            return

        file_id = msg.get("file_id")
        bubble = self._file_bubbles.get(file_id) if file_id else None
        if bubble:
            bubble.set_download_status("Lädt...")
            bubble.set_download_progress(0)

        worker = DownloadWorker(url, str(dest_path), filename)
        worker.progress.connect(
            lambda name, pct: self._update_download_progress(bubble, name, pct)
        )
        worker.finished.connect(lambda name, p: self._finish_download(bubble, name, p, filename))
        worker.failed.connect(lambda name, err: self._fail_download(bubble, name))
        worker.finished.connect(lambda *_: self._cleanup_worker())
        worker.failed.connect(lambda *_: self._cleanup_worker())
        self._download_threads.append(worker)
        worker.start()

    def _ensure_image_preview(self, msg: dict, bubble: ChatBubble) -> None:
        filename = msg.get("filename") or ""
        file_id = msg.get("file_id") or ""
        if not _is_image_file(filename) or not file_id:
            return
        cache_path = attachment_cache_path(file_id, filename)
        if cache_path.exists():
            bubble.set_image_preview(str(cache_path))
            return
        if msg.get("_from_history"):
            return

        url = msg.get("url") or ""
        if not url:
            return
        parsed = urllib.parse.urlparse(url)
        if not parsed.netloc:
            sender_ip = msg.get("sender_ip") or ""
            if not sender_ip:
                return
            url = f"http://{sender_ip}{parsed.path}"

        worker = ImageFetchWorker(url, str(cache_path))
        worker.finished.connect(lambda path: bubble.set_image_preview(path))
        worker.finished.connect(lambda _: self._cleanup_image_workers())
        worker.failed.connect(lambda _: self._cleanup_image_workers())
        self._image_fetch_threads.append(worker)
        worker.start()

    def _open_image_preview(self, image_path: str) -> None:
        dialog = ImagePreviewDialog(image_path, self)
        dialog.exec()

    def _cleanup_image_workers(self) -> None:
        self._image_fetch_threads = [w for w in self._image_fetch_threads if w.isRunning()]

    def _update_download_progress(self, bubble: ChatBubble | None, name: str, pct: int) -> None:
        if bubble:
            bubble.set_download_progress(pct)
        self.status_label.setText(f"Lädt: {name} ({pct}%)")

    def _finish_download(self, bubble: ChatBubble | None, name: str, path: str, filename: str) -> None:
        if bubble:
            bubble.set_download_status("Gespeichert")
            bubble.set_download_progress(100)
            if _is_image_file(filename):
                bubble.set_image_preview(path)
        self.status_label.setText(f"Fertig: {name}")

    def _fail_download(self, bubble: ChatBubble | None, name: str) -> None:
        if bubble:
            bubble.set_download_status("Fehler")
        self.status_label.setText(f"Fehler: {name}")

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


def _trim_text(text: str, max_len: int = 120) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"


def _is_image_file(filename: str) -> bool:
    suffix = Path(filename).suffix.lower()
    return suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
