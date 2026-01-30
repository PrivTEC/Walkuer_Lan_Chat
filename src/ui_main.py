from __future__ import annotations

import ctypes
import gzip
import hashlib
import html
import io
import json
import os
import time
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, Signal, QSize, QEvent, QPoint, QRect, QRectF, QUrl
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
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
import theme as theme_mod
from config_store import ConfigStore
from net import protocol
from util.images import load_avatar_pixmap, generate_qr_pixmap
from util.i18n import t
from util.markdown_render import render_markdown, extract_first_url
from util.paths import attachment_cache_path, downloads_dir, logs_dir
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


class LinkThumbFetchWorker(QThread):
    finished = Signal(str, str)
    failed = Signal(str, str)

    def __init__(self, url: str, dest_path: str, file_id: str, source_url: str) -> None:
        super().__init__()
        self._url = url
        self._dest_path = dest_path
        self._file_id = file_id
        self._source_url = source_url

    def run(self) -> None:
        try:
            req = urllib.request.Request(self._url, headers=_LINKPREVIEW_IMAGE_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content_type = (resp.headers.get("Content-Type") or "").lower()
                if "text/html" in content_type:
                    raise RuntimeError("unexpected html response")
                max_bytes = 3 * 1024 * 1024
                data = bytearray()
                while len(data) < max_bytes:
                    chunk = resp.read(1024 * 64)
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) >= max_bytes:
                        raise RuntimeError("image too large")
            if not data:
                raise RuntimeError("empty image response")
            Path(self._dest_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self._dest_path, "wb") as f:
                f.write(data)
            _write_thumb_src(self._file_id, self._source_url)
            self.finished.emit(self._dest_path, self._source_url)
        except Exception as exc:
            self.failed.emit(self._dest_path, str(exc))


class _LinkPreviewHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.base_href = ""
        self.link_canonical = ""
        self.link_image_src = ""
        self.link_icon = ""
        self.link_apple_icon = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = (tag or "").lower()
        attrs_map = {str(k).lower(): v for k, v in attrs if k}
        if tag == "meta":
            key = (
                attrs_map.get("property")
                or attrs_map.get("name")
                or attrs_map.get("itemprop")
                or ""
            )
            key = key.lower()
            content = (attrs_map.get("content") or attrs_map.get("href") or "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = html.unescape(content)
        elif tag == "link":
            rel = (attrs_map.get("rel") or "").lower()
            href = (attrs_map.get("href") or attrs_map.get("content") or "").strip()
            if not href:
                return
            if "canonical" in rel and not self.link_canonical:
                self.link_canonical = html.unescape(href)
            if "image_src" in rel and not self.link_image_src:
                self.link_image_src = html.unescape(href)
            if "apple-touch-icon" in rel and not self.link_apple_icon:
                self.link_apple_icon = html.unescape(href)
            if "icon" in rel and not self.link_icon:
                self.link_icon = html.unescape(href)
        elif tag == "title":
            self._in_title = True
        elif tag == "base":
            href = (attrs_map.get("href") or "").strip()
            if href and not self.base_href:
                self.base_href = href

    def handle_endtag(self, tag: str) -> None:
        if (tag or "").lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and data:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return html.unescape("".join(self.title_parts)).strip()


class LinkPreviewWorker(QThread):
    finished = Signal(str, dict)
    failed = Signal(str, str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    def run(self) -> None:
        try:
            target_url = _normalize_preview_url(self._url)
            def fetch_html(url: str, headers: dict[str, str]) -> tuple[str, str, str]:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    max_bytes = 512 * 1024
                    data = bytearray()
                    while len(data) < max_bytes:
                        chunk = resp.read(1024 * 64)
                        if not chunk:
                            break
                        data.extend(chunk)
                        if len(data) >= max_bytes:
                            break
                    final = resp.geturl() or url
                    charset = resp.headers.get_content_charset() or "utf-8"
                    enc = (resp.headers.get("Content-Encoding") or "").lower()
                raw = bytes(data)
                if enc:
                    try:
                        if "gzip" in enc:
                            raw = gzip.decompress(raw)
                        elif "deflate" in enc:
                            try:
                                raw = zlib.decompress(raw)
                            except zlib.error:
                                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                        elif "br" in enc:
                            raise RuntimeError("brotli unsupported")
                    except Exception as exc:
                        _log_link_preview(f"linkpreview_fail url={url} reason=decompress:{exc}")
                        raise
                return raw.decode(charset, errors="replace"), final, enc

            html_text, final_url, encoding = fetch_html(target_url, _LINKPREVIEW_HTML_HEADERS)
            parser = _LinkPreviewHTMLParser()
            parser.feed(html_text)
            parser.close()
            meta = parser.meta

            title = _first_meta_value(meta, ["og:title", "twitter:title", "title"])
            if not title:
                title = parser.title or ""
            description = _first_meta_value(
                meta,
                ["og:description", "twitter:description", "description"],
            )
            site_name = meta.get("og:site_name") or ""
            canonical_url = _first_meta_value(meta, ["og:url"]) or parser.link_canonical or ""
            base_url = parser.base_href or final_url or target_url
            canonical_url = _resolve_url(base_url, canonical_url or final_url or target_url)

            image_url, image_reason, has_strong = _pick_image_url(
                meta,
                parser,
                base_url,
                canonical_url,
                target_url,
            )

            if not has_strong and _is_facebook_host(canonical_url or target_url):
                fb_headers = dict(_LINKPREVIEW_HTML_HEADERS)
                fb_headers["User-Agent"] = _FACEBOOK_UA
                html_text, final_url, encoding = fetch_html(target_url, fb_headers)
                parser = _LinkPreviewHTMLParser()
                parser.feed(html_text)
                parser.close()
                meta = parser.meta
                title = _first_meta_value(meta, ["og:title", "twitter:title", "title"]) or parser.title or title
                description = _first_meta_value(
                    meta,
                    ["og:description", "twitter:description", "description"],
                ) or description
                site_name = meta.get("og:site_name") or site_name
                base_url = parser.base_href or final_url or target_url
                canonical_url = _resolve_url(
                    base_url,
                    _first_meta_value(meta, ["og:url"]) or parser.link_canonical or canonical_url,
                )
                image_url, image_reason, has_strong = _pick_image_url(
                    meta,
                    parser,
                    base_url,
                    canonical_url,
                    target_url,
                )

            yt_id = _extract_youtube_id(canonical_url or target_url)
            if yt_id:
                oembed = _fetch_youtube_oembed(canonical_url or target_url)
                if oembed:
                    if oembed.get("title"):
                        title = oembed["title"]
                    if oembed.get("thumbnail_url"):
                        image_url = oembed["thumbnail_url"]
                        image_reason = "yt_oembed"
                if (not image_url or _is_favicon_url(image_url)) and yt_id:
                    image_url = f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg"
                    if not image_reason or image_reason in {"favicon", "icon"}:
                        image_reason = "yt_oembed"

            title = _trim_text(_clean_text(title), 80)
            description = _trim_text(_clean_text(description), 160)
            site_name = _trim_text(_clean_text(site_name), 80)

            if not title:
                title = _display_url(canonical_url)

            _log_link_preview(
                f"linkpreview_pick url={canonical_url or target_url} "
                f"chosen_image={image_url or ''} reason={image_reason or ''}"
            )

            preview = {
                "url": canonical_url,
                "display_url": _display_url(canonical_url or target_url),
                "title": title,
                "description": description,
                "site_name": site_name,
                "image_url": image_url,
                "_encoding": encoding,
            }
            self.finished.emit(self._url, preview)
        except Exception as exc:
            _log_link_preview(f"linkpreview_fail url={self._url} reason={exc}")
            self.failed.emit(self._url, str(exc))


class LinkThumbWorker(QThread):
    finished = Signal(str, str, str)
    failed = Signal(str, str)

    def __init__(self, image_url: str, page_url: str, file_id: str) -> None:
        super().__init__()
        self._image_url = image_url
        self._page_url = page_url
        self._file_id = file_id

    def run(self) -> None:
        try:
            thumb_path, err = create_link_thumb(self._image_url, self._page_url, self._file_id)
            if not thumb_path:
                raise RuntimeError(err or "thumbnail unavailable")
            self.finished.emit(self._page_url, self._file_id, thumb_path)
        except Exception as exc:
            self.failed.emit(self._page_url, str(exc))


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):  # noqa: N802 - Qt naming
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ClickableFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event):  # noqa: N802 - Qt naming
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ImagePreviewDialog(QDialog):
    def __init__(self, image_path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("preview.title"))
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
            label.setText(t("preview.unavailable"))
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
        self._raw_name = name or ""
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
        raw_name = name or t("user.unknown")
        self._raw_name = raw_name
        label = raw_name
        if self._is_self:
            label = t("user.self", name=raw_name)
        self._name_label.setText(label)

        pixmap = load_avatar_pixmap(avatar_path, name, avatar_sha, 28)
        self._avatar.setPixmap(pixmap)

        if typing:
            self._status_label.setText(t("user.typing"))
            self._status_label.setObjectName("userStatusTyping")
        else:
            time_stamp = fmt_time_seconds(last_seen) if last_seen else ""
            suffix = t("user.last_seen", time=time_stamp) if time_stamp else ""
            self._status_label.setText(t("user.online") + suffix)
            self._status_label.setObjectName("userStatus")
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)

    def refresh_avatar(self, avatar_path: str, avatar_sha: str, name: str) -> None:
        self.avatar_sha = avatar_sha
        pixmap = load_avatar_pixmap(avatar_path, name, avatar_sha, 28)
        self._avatar.setPixmap(pixmap)

    def raw_name(self) -> str:
        return self._raw_name


class ChatBubble(QFrame):
    TAIL_OUT = 12
    TAIL_H = 18
    RADIUS = 12
    BORDER_W = 1
    REPLY_GAP_PX = 8

    reply_requested = Signal(dict)
    reaction_requested = Signal(dict, str)
    download_requested = Signal(dict)
    image_clicked = Signal(str)
    edit_requested = Signal(dict)
    undo_requested = Signal(dict)
    pin_requested = Signal(dict)
    unpin_requested = Signal(dict)

    def __init__(self, msg: dict, is_self: bool, theme_key: str, parent=None) -> None:
        super().__init__(parent)
        self.msg = msg
        self._reactions: dict[str, set[str]] = {}
        self._file_status: QLabel | None = None
        self._preview_label: ClickableLabel | None = None
        self._preview_path: str | None = None
        self._text_widget: QLabel | None = None
        self._qr_label: QLabel | None = None
        self._qr_url: str | None = None
        self._qr_btn: QToolButton | None = None
        self._qr_visible = False
        self._reply_btn: QToolButton | None = None
        self._react_btn: QToolButton | None = None
        self._reply_name_label: QLabel | None = None
        self._reply_preview: QLabel | None = None
        self._time_label: QLabel | None = None
        self._link_preview_card: ClickableFrame | None = None
        self._link_preview_url: str | None = None
        self._link_preview_thumb: QLabel | None = None
        self._link_preview_qr_btn: QToolButton | None = None
        self._lp_thumb_worker: LinkThumbFetchWorker | None = None
        self._has_link_preview = False
        self._is_self = is_self
        self._theme_key = theme_key
        self._pinned = False
        self._progress: QProgressBar | None = None
        self._retry_btn: QPushButton | None = None
        self._download_btn: QPushButton | None = None
        self._file_status_key = "file.ready"
        self._download_pct: int | None = None

        self.setObjectName("chatBubbleSelf" if is_self else "chatBubble")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)

        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        base_left = 12
        base_right = 12
        tail_out = self.TAIL_OUT
        if is_self:
            layout.setContentsMargins(base_left, 10, base_right + tail_out, 10)
        else:
            layout.setContentsMargins(base_left + tail_out, 10, base_right, 10)

        body = QVBoxLayout()
        body.setSpacing(6)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(msg.get("name") or t("user.unknown"))
        name_label.setObjectName("nameLabel")
        self._time_label = QLabel(fmt_time(msg.get("ts") or 0))
        self._time_label.setObjectName("timeLabel")

        self._reply_btn = QToolButton()
        self._reply_btn.setObjectName("replyButton")
        self._reply_btn.setText("↩")
        self._reply_btn.setToolTip(t("chat.reply"))
        self._reply_btn.clicked.connect(lambda: self.reply_requested.emit(self.msg))

        self._react_btn = QToolButton()
        self._react_btn.setObjectName("reactionButton")
        self._react_btn.setText("★")
        self._react_btn.setToolTip(t("chat.react"))
        self._react_btn.clicked.connect(self._open_reaction_menu)

        self._qr_btn = QToolButton()
        self._qr_btn.setObjectName("qrToggleButton")
        self._qr_btn.setText("QR")
        self._qr_btn.setToolTip(t("qr.show"))
        self._qr_btn.clicked.connect(self._toggle_qr)
        self._qr_btn.hide()

        header.addWidget(name_label)
        header.addStretch(1)
        header.addWidget(self._qr_btn)
        header.addWidget(self._reply_btn)
        header.addWidget(self._react_btn)
        body.addLayout(header)

        reply_to = msg.get("reply_to")
        if reply_to:
            reply_box = QFrame()
            reply_box.setObjectName("replyBox")
            reply_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            reply_layout = QVBoxLayout(reply_box)
            reply_layout.setContentsMargins(8, 6, 8, 6)
            reply_layout.setSpacing(2)
            self._reply_name_label = QLabel(msg.get("reply_name") or t("chat.reply_label"))
            self._reply_name_label.setObjectName("replyName")
            self._reply_preview = QLabel()
            self._reply_preview.setObjectName("replyPreview")
            self._reply_preview.setText(_trim_text(msg.get("reply_preview") or ""))
            self._reply_preview.setWordWrap(True)
            self._reply_preview.setMinimumWidth(0)
            self._reply_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            self._update_reply_preview_height()
            reply_layout.addWidget(self._reply_name_label)
            reply_layout.addWidget(self._reply_preview)
            body.addWidget(reply_box)
            body.addSpacing(self.REPLY_GAP_PX)

        if msg.get("t") == "CHAT":
            link_preview = msg.get("link_preview")
            if isinstance(link_preview, dict):
                self._has_link_preview = True
                self._build_link_preview_card(link_preview, body)

            self._text_widget = QLabel()
            self._text_widget.setObjectName("chatText")
            self._text_widget.setTextFormat(Qt.RichText)
            self._text_widget.setOpenExternalLinks(True)
            self._text_widget.setTextInteractionFlags(Qt.TextBrowserInteraction)
            self._text_widget.setWordWrap(True)
            self._text_widget.setStyleSheet("margin: 0px;")
            self._text_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self._text_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            self._text_widget.customContextMenuRequested.connect(
                lambda pos: self._show_context_menu(self._text_widget.mapToGlobal(pos))
            )
            body.addWidget(self._text_widget)

            self._qr_label = QLabel()
            self._qr_label.setObjectName("qrCode")
            self._qr_label.setFixedSize(128, 128)
            self._qr_label.setAlignment(Qt.AlignCenter)
            self._qr_label.setScaledContents(False)
            self._qr_label.hide()
            align = Qt.AlignRight if self._is_self else Qt.AlignLeft
            body.addWidget(self._qr_label, alignment=align)

            self._set_text_content(msg.get("text") or "", bool(msg.get("deleted")))
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
            self._file_status_key = "file.ready"
            self._file_status = QLabel(t(self._file_status_key))
            self._file_status.setObjectName("fileStatus")
            self._download_btn = QPushButton(t("file.download"))
            self._download_btn.setObjectName("downloadButton")
            self._download_btn.clicked.connect(lambda: self.download_requested.emit(msg))
            self._retry_btn = QPushButton(t("file.retry"))
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

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addStretch(1)
        footer.addWidget(self._time_label)
        body.addLayout(footer)

        layout.addLayout(body, 1)
        self._update_time_label()

    def resizeEvent(self, event):  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self._update_reply_preview_height()

    def apply_translations(self) -> None:
        if self._reply_btn is not None:
            self._reply_btn.setToolTip(t("chat.reply"))
        if self._react_btn is not None:
            self._react_btn.setToolTip(t("chat.react"))
        if self._qr_btn is not None:
            self._qr_btn.setToolTip(t("qr.show"))
        if self._link_preview_qr_btn is not None:
            self._link_preview_qr_btn.setToolTip(t("qr.show"))
        if self._reply_name_label is not None and not self.msg.get("reply_name"):
            self._reply_name_label.setText(t("chat.reply_label"))
        if self._download_btn is not None:
            self._download_btn.setText(t("file.download"))
        if self._retry_btn is not None:
            self._retry_btn.setText(t("file.retry"))
        if self._file_status is not None:
            if self._file_status_key == "download.loading" and self._download_pct is not None:
                self._file_status.setText(t("download.loading_progress", percent=self._download_pct))
            else:
                self._file_status.setText(t(self._file_status_key))
        self._set_text_content(self.msg.get("text") or "", bool(self.msg.get("deleted")))
        self._update_time_label()
        self._refresh_qr_buttons(bool(self._qr_url))

    def paintEvent(self, event):  # noqa: N802 - Qt naming
        # Tail is painted here so it remains part of the bubble contour without extra widgets.
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        colors = theme_mod.get_bubble_colors(self._theme_key)
        bg = colors.get("bubble_self_bg") if self._is_self else colors.get("bubble_bg")
        border = colors.get("bubble_self_border") if self._is_self else colors.get("bubble_border")
        if self.property("flash") is True:
            border = colors.get("neon_green", "#39ff14")

        bw = float(self.BORDER_W)
        tail_y = max(self.RADIUS + 6, h - self.TAIL_H - 10)
        tail_mid = tail_y + (self.TAIL_H / 2.0)
        tail_y2 = tail_y + self.TAIL_H

        if self._is_self:
            body_rect = QRectF(0, 0, w - self.TAIL_OUT, h)
            base_x = w - self.TAIL_OUT
            tip_x = w
            dir_sign = 1.0
        else:
            body_rect = QRectF(self.TAIL_OUT, 0, w - self.TAIL_OUT, h)
            base_x = self.TAIL_OUT
            tip_x = 0
            dir_sign = -1.0

        body_rect = body_rect.adjusted(bw / 2, bw / 2, -bw / 2, -bw / 2)
        body_path = QPainterPath()
        body_path.addRoundedRect(body_rect, self.RADIUS, self.RADIUS)

        ctrl_x = base_x + dir_sign * (self.TAIL_OUT * 0.45)
        tail_path = QPainterPath()
        tail_path.moveTo(base_x, tail_y)
        tail_path.cubicTo(ctrl_x, tail_y + self.TAIL_H * 0.2, tip_x, tail_mid - self.TAIL_H * 0.2, tip_x, tail_mid)
        tail_path.cubicTo(tip_x, tail_mid + self.TAIL_H * 0.2, ctrl_x, tail_y2 - self.TAIL_H * 0.2, base_x, tail_y2)
        tail_path.closeSubpath()

        shape = body_path.united(tail_path)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillPath(shape, QColor(bg))
        pen = QPen(QColor(border), bw)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawPath(shape)

    def _update_reply_preview_height(self) -> None:
        if not self._reply_preview:
            return
        width = self._reply_preview.width()
        if width <= 0:
            return
        metrics = self._reply_preview.fontMetrics()
        rect = metrics.boundingRect(0, 0, width, 10_000, Qt.TextWordWrap, self._reply_preview.text())
        target = rect.height() + 2
        if self._reply_preview.minimumHeight() != target:
            self._reply_preview.setMinimumHeight(target)
            self._reply_preview.updateGeometry()

    def contextMenuEvent(self, event):  # noqa: N802 - Qt naming
        self._show_context_menu(event.globalPos())

    def _show_context_menu(self, global_pos) -> None:
        menu = QMenu(self)
        copy_action = menu.addAction(t("menu.copy"))
        edit_action = None
        undo_action = None
        pin_action = None
        if self._is_self and not self.msg.get("deleted") and self.msg.get("t") == "CHAT":
            edit_action = menu.addAction(t("menu.edit"))
            undo_action = menu.addAction(t("menu.undo"))
        if self._pinned:
            pin_action = menu.addAction(t("menu.unpin"))
        else:
            pin_action = menu.addAction(t("menu.pin"))
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
        return

    def set_download_status(self, key: str) -> None:
        self._file_status_key = key
        if key != "download.loading":
            self._download_pct = None
        text = t(key)
        if self._file_status is not None:
            self._file_status.setText(text)
        if self._download_btn is not None:
            self._download_btn.setEnabled(key != "download.loading")
        if self._retry_btn is not None:
            self._retry_btn.setVisible(key == "download.error")
        if self._progress is not None:
            if key == "download.loading":
                self._progress.show()
            else:
                self._progress.hide()

    def set_download_progress(self, pct: int) -> None:
        self._file_status_key = "download.loading"
        self._download_pct = pct
        if self._progress is not None:
            self._progress.setValue(pct)
            if pct >= 100:
                self._progress.hide()
            else:
                self._progress.show()
        if self._file_status is not None:
            self._file_status.setText(t("download.loading_progress", percent=pct))
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

    def _build_link_preview_card(self, preview: dict, body_layout: QVBoxLayout) -> None:
        url = (preview.get("url") or "").strip()
        display_url = (preview.get("display_url") or "").strip()
        site_name = (preview.get("site_name") or "").strip()
        title = (preview.get("title") or "").strip()
        description = (preview.get("description") or "").strip()

        self._link_preview_url = url

        domain = site_name or display_url or _display_url(url)
        if not domain:
            domain = _display_url(url) if url else ""

        card = ClickableFrame()
        card.setObjectName("linkPreviewCard")
        card.setCursor(Qt.PointingHandCursor)
        card.clicked.connect(self._open_link_preview)
        if url:
            card.setToolTip(url)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(8)

        self._link_preview_thumb = QLabel()
        self._link_preview_thumb.setObjectName("linkPreviewThumb")
        self._link_preview_thumb.setFixedSize(72, 72)
        self._link_preview_thumb.setScaledContents(False)
        self._link_preview_thumb.hide()

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        domain_label = QLabel(domain)
        domain_label.setObjectName("linkPreviewDomain")
        title_label = QLabel(title or display_url or url)
        title_label.setObjectName("linkPreviewTitle")
        title_label.setWordWrap(True)
        desc_label = QLabel(description)
        desc_label.setObjectName("linkPreviewDesc")
        desc_label.setWordWrap(True)
        if not description:
            desc_label.hide()
        text_layout.addWidget(domain_label)
        text_layout.addWidget(title_label)
        text_layout.addWidget(desc_label)

        for label in (domain_label, title_label, desc_label, self._link_preview_thumb):
            label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._link_preview_qr_btn = QToolButton()
        self._link_preview_qr_btn.setObjectName("linkPreviewQRBtn")
        self._link_preview_qr_btn.setText("QR")
        self._link_preview_qr_btn.setToolTip(t("qr.show"))
        self._link_preview_qr_btn.clicked.connect(self._toggle_qr)

        card_layout.addWidget(self._link_preview_thumb)
        card_layout.addLayout(text_layout, 1)
        card_layout.addWidget(self._link_preview_qr_btn)

        self._link_preview_card = card
        body_layout.addWidget(card)

        self._load_link_preview_thumb(preview)
        self._refresh_qr_buttons(bool(url))

    def _load_link_preview_thumb(self, preview: dict) -> None:
        if not self._link_preview_thumb:
            return
        thumb_url = (preview.get("thumb_url") or "").strip()
        thumb_file_id = (preview.get("thumb_file_id") or "").strip()
        if not thumb_file_id:
            thumb_file_id = _link_thumb_file_id(preview.get("url") or "")
        if not thumb_url or not thumb_file_id:
            self._link_preview_thumb.hide()
            return
        cache_path = attachment_cache_path(thumb_file_id, "thumb.jpg")
        if _is_thumb_cache_valid(thumb_file_id, thumb_url):
            _log_thumb_cache(thumb_file_id, reused=True, src_changed=False)
            self._apply_link_preview_thumb(str(cache_path))
            return
        if cache_path.exists():
            _log_thumb_cache(thumb_file_id, reused=False, src_changed=True)
        else:
            _log_thumb_cache(thumb_file_id, reused=False, src_changed=False)
        if self.msg.get("_from_history"):
            self._link_preview_thumb.hide()
            return
        self._set_link_preview_thumb_placeholder("...")
        worker = LinkThumbFetchWorker(thumb_url, str(cache_path), thumb_file_id, thumb_url)
        worker.finished.connect(lambda path, _src: self._apply_link_preview_thumb(path))
        worker.finished.connect(lambda _: self._clear_link_preview_worker())
        worker.failed.connect(self._on_link_preview_thumb_failed)
        worker.failed.connect(lambda *_: self._clear_link_preview_worker())
        self._lp_thumb_worker = worker
        worker.start()

    def _apply_link_preview_thumb(self, path: str) -> None:
        if not self._link_preview_thumb:
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        _set_cover_pixmap(self._link_preview_thumb, pixmap)
        self._link_preview_thumb.setText("")
        self._link_preview_thumb.setToolTip("")
        self._link_preview_thumb.show()

    def _set_link_preview_thumb_placeholder(self, text: str) -> None:
        if not self._link_preview_thumb:
            return
        self._link_preview_thumb.setText(text)
        self._link_preview_thumb.setAlignment(Qt.AlignCenter)
        self._link_preview_thumb.setToolTip(t("linkpreview.loading_image"))
        self._link_preview_thumb.show()

    def _on_link_preview_thumb_failed(self, _path: str, reason: str) -> None:
        if not self._link_preview_thumb:
            return
        message = (
            t("linkpreview.thumbnail_unavailable_reason", reason=reason)
            if reason
            else t("linkpreview.thumbnail_unavailable")
        )
        self._link_preview_thumb.setText("!")
        self._link_preview_thumb.setAlignment(Qt.AlignCenter)
        self._link_preview_thumb.setToolTip(message)
        self._link_preview_thumb.show()
        _log_link_preview(f"linkpreview_thumb_fail url={self._link_preview_url or ''} reason={reason}")

    def _clear_link_preview_worker(self) -> None:
        if self._lp_thumb_worker and not self._lp_thumb_worker.isRunning():
            self._lp_thumb_worker = None

    def _set_text_content(self, text: str, deleted: bool) -> None:
        if not self._text_widget:
            return
        if deleted:
            self._text_widget.setText(t("chat.message_deleted_html"))
            self._text_widget.setObjectName("chatTextMuted")
            self._update_qr_code("")
        else:
            self._text_widget.setText(render_markdown(text))
            self._text_widget.setObjectName("chatText")
            self._update_qr_code(text)
        self._text_widget.style().unpolish(self._text_widget)
        self._text_widget.style().polish(self._text_widget)
        self._text_widget.updateGeometry()

    def _update_time_label(self) -> None:
        if not self._time_label:
            return
        label = fmt_time(self.msg.get("ts") or 0)
        if self.msg.get("edited"):
            label = t("chat.edited_time", time=label)
        self._time_label.setText(label)

    def _open_link_preview(self) -> None:
        url = (self._link_preview_url or "").strip()
        if not url:
            return
        QDesktopServices.openUrl(QUrl(url))

    def _refresh_qr_buttons(self, available: bool) -> None:
        label = t("qr.hide") if self._qr_visible else t("qr.show")
        if self._qr_btn is not None:
            self._qr_btn.setVisible(available and not self._has_link_preview)
            self._qr_btn.setToolTip(label)
        if self._link_preview_qr_btn is not None:
            self._link_preview_qr_btn.setVisible(available and self._has_link_preview)
            self._link_preview_qr_btn.setToolTip(label)

    def _toggle_qr(self) -> None:
        if not self._qr_label:
            return
        if not self._qr_url:
            self._update_qr_code(self.msg.get("text") or "")
            if not self._qr_url:
                return
        self._qr_visible = not self._qr_visible
        self._qr_label.setVisible(self._qr_visible)
        self._refresh_qr_buttons(True)

    def _update_qr_code(self, text: str) -> None:
        if not self._qr_label:
            return
        if self.msg.get("deleted"):
            url = ""
        else:
            url = self._link_preview_url or extract_first_url(text)
        if not url:
            self._qr_label.hide()
            self._qr_label.clear()
            self._qr_url = None
            self._qr_visible = False
            self._refresh_qr_buttons(False)
            return
        if url != self._qr_url or self._qr_label.pixmap() is None:
            pixmap = generate_qr_pixmap(url, 120)
            if pixmap is None or pixmap.isNull():
                self._qr_label.hide()
                self._qr_label.clear()
                self._qr_url = None
                self._qr_visible = False
                self._refresh_qr_buttons(False)
                return
            self._qr_url = url
            self._qr_label.setPixmap(pixmap)
            self._qr_visible = False
        self._refresh_qr_buttons(True)
        self._qr_label.setVisible(self._qr_visible)

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
        self._lp_current_url: str | None = None
        self._lp_dismissed_url: str | None = None
        self._lp_failed_url: str | None = None
        self._lp_data: dict | None = None
        self._lp_worker: LinkPreviewWorker | None = None
        self._lp_workers: list[LinkPreviewWorker] = []
        self._lp_thumb_worker: LinkThumbWorker | None = None
        self._lp_thumb_workers: list[LinkThumbWorker] = []
        self._lp_thumb_path: str | None = None
        self._lp_thumb_file_id: str | None = None
        self._lp_thumb_url: str | None = None
        self._lp_thumb_error: str | None = None

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

        self._title_label = QLabel(t("app.short_title"))
        self._title_label.setObjectName("appTitle")

        style = self.style()

        self._settings_btn = QToolButton()
        self._settings_btn.setText("⚙")
        self._settings_btn.setToolTip(t("settings.title"))
        self._settings_btn.clicked.connect(self.open_settings)
        self._minimize_btn = QToolButton()
        self._minimize_btn.setIcon(style.standardIcon(QStyle.SP_TitleBarMinButton))
        self._minimize_btn.setIconSize(QSize(12, 12))
        self._minimize_btn.setToolTip(t("window.minimize"))
        self._minimize_btn.clicked.connect(self.showMinimized)
        self._max_btn = QToolButton()
        self._max_btn.setIcon(style.standardIcon(QStyle.SP_TitleBarMaxButton))
        self._max_btn.setIconSize(QSize(12, 12))
        self._max_btn.setToolTip(t("window.maximize"))
        self._max_btn.clicked.connect(self._toggle_maximize)
        self._close_btn = QToolButton()
        self._close_btn.setIcon(style.standardIcon(QStyle.SP_TitleBarCloseButton))
        self._close_btn.setIconSize(QSize(12, 12))
        self._close_btn.setToolTip(t("common.close"))
        self._close_btn.clicked.connect(self._hide_to_tray)

        top_layout.addWidget(icon_label)
        top_layout.addWidget(self._title_label)
        top_layout.addStretch(1)
        top_layout.addWidget(self._settings_btn)
        top_layout.addWidget(self._minimize_btn)
        top_layout.addWidget(self._max_btn)
        top_layout.addWidget(self._close_btn)

        self._topbar = topbar
        self._title_controls = {self._settings_btn, self._minimize_btn, self._max_btn, self._close_btn}
        self._resize_margin = 6
        self._resize_edges = Qt.Edges()
        self._use_native_frame = False
        self._normal_geometry: QRect | None = None
        self._pending_normal_geometry: QRect | None = None
        self._pending_geometry_attempts = 0

        self._drag_widgets = {topbar, self._title_label, icon_label}
        for widget in self._drag_widgets:
            widget.installEventFilter(self)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

        self._header_label = QLabel(t("app.org_name"))
        self._header_label.setObjectName("headerTitle")
        self._header_label.setAlignment(Qt.AlignCenter)
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(14)
        glow.setColor(Qt.green)
        glow.setOffset(0, 0)
        self._header_label.setGraphicsEffect(glow)

        meta_bar = QFrame()
        meta_bar.setObjectName("metaBar")
        meta_layout = QHBoxLayout(meta_bar)
        meta_layout.setContentsMargins(4, 0, 4, 0)
        meta_layout.setSpacing(8)

        self.online_label = QLabel(t("status.online_count", count=1))
        self.online_label.setObjectName("onlineLabel")
        self.online_label.setAlignment(Qt.AlignLeft)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText(t("search.placeholder"))
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

        self._user_title = QLabel(t("user.list_title"))
        self._user_title.setObjectName("userListTitle")

        self.user_list_area = QScrollArea()
        self.user_list_area.setWidgetResizable(True)
        self.user_list_area.setFrameShape(QFrame.NoFrame)

        self.user_list_container = QWidget()
        self.user_list_layout = QVBoxLayout(self.user_list_container)
        self.user_list_layout.setContentsMargins(0, 0, 0, 0)
        self.user_list_layout.setSpacing(6)
        self.user_list_layout.addStretch(1)
        self.user_list_area.setWidget(self.user_list_container)

        user_layout.addWidget(self._user_title)
        user_layout.addWidget(self.user_list_area, 1)

        chat_panel = QFrame()
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(8)

        self.chat_area = QScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_area.setFrameShape(QFrame.NoFrame)
        self.chat_area.setStyleSheet("background: transparent;")
        self.chat_area.viewport().setAutoFillBackground(False)

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

        self.chat_stack = QFrame()
        self.chat_stack.setObjectName("chatStack")
        chat_stack_layout = QGridLayout(self.chat_stack)
        chat_stack_layout.setContentsMargins(0, 0, 0, 0)
        chat_stack_layout.setSpacing(0)

        self._chat_bg_color = QFrame()
        self._chat_bg_color.setObjectName("chatBgColor")
        self._chat_bg_image = QLabel()
        self._chat_bg_image.setAlignment(Qt.AlignCenter)
        self._chat_bg_image.setScaledContents(False)
        self._chat_bg_image_fx = QGraphicsOpacityEffect(self._chat_bg_image)
        self._chat_bg_image.setGraphicsEffect(self._chat_bg_image_fx)
        self._chat_bg_pixmap: QPixmap | None = None
        self._chat_bg_path: str = ""

        chat_stack_layout.addWidget(self._chat_bg_color, 0, 0)
        chat_stack_layout.addWidget(self._chat_bg_image, 0, 0)
        chat_stack_layout.addWidget(self.chat_area, 0, 0)
        self.chat_area.raise_()

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
        self.pinned_clear_btn.setToolTip(t("pin.clear_tooltip"))
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

        self.link_preview_bar = QFrame()
        self.link_preview_bar.setObjectName("composerLinkPreview")
        lp_layout = QHBoxLayout(self.link_preview_bar)
        lp_layout.setContentsMargins(10, 8, 10, 8)
        lp_layout.setSpacing(8)

        self.lp_thumb_label = QLabel()
        self.lp_thumb_label.setObjectName("lpThumb")
        self.lp_thumb_label.setFixedSize(52, 52)
        self.lp_thumb_label.setScaledContents(False)
        self.lp_thumb_label.hide()

        lp_text_col = QVBoxLayout()
        lp_text_col.setSpacing(2)
        self.lp_domain_label = QLabel("")
        self.lp_domain_label.setObjectName("lpDomain")
        self.lp_title_label = QLabel("")
        self.lp_title_label.setObjectName("lpTitle")
        self.lp_title_label.setWordWrap(True)
        self.lp_desc_label = QLabel("")
        self.lp_desc_label.setObjectName("lpDesc")
        self.lp_desc_label.setWordWrap(True)
        lp_text_col.addWidget(self.lp_domain_label)
        lp_text_col.addWidget(self.lp_title_label)
        lp_text_col.addWidget(self.lp_desc_label)

        self.lp_close_btn = QToolButton()
        self.lp_close_btn.setObjectName("lpClose")
        self.lp_close_btn.setText("X")
        self.lp_close_btn.setToolTip(t("linkpreview.close"))
        self.lp_close_btn.clicked.connect(self._dismiss_link_preview)

        lp_layout.addWidget(self.lp_thumb_label)
        lp_layout.addLayout(lp_text_col, 1)
        lp_layout.addWidget(self.lp_close_btn)
        self.link_preview_bar.hide()

        composer = QFrame()
        composer.setObjectName("composerBar")
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(8, 8, 8, 8)
        composer_layout.setSpacing(8)

        self._attach_btn = QPushButton()
        self._attach_btn.setObjectName("iconButton")
        self._attach_btn.setText("📎")
        self._attach_btn.setToolTip(t("composer.attach"))
        self._attach_btn.setFixedSize(40, 40)
        self._attach_btn.clicked.connect(self._choose_files)

        self.text_input = SendTextEdit()
        self.text_input.setPlaceholderText(t("composer.placeholder"))
        self.text_input.setFixedHeight(80)
        self.text_input.setAcceptDrops(False)
        self.text_input.send_requested.connect(self._send_clicked)
        self.text_input.textChanged.connect(self._on_text_changed)

        self._send_btn = QPushButton(t("composer.send"))
        self._send_btn.setObjectName("primaryButton")
        self._send_btn.setFixedWidth(110)
        self._send_btn.clicked.connect(self._send_clicked)

        composer_layout.addWidget(self._attach_btn)
        composer_layout.addWidget(self.text_input, 1)
        composer_layout.addWidget(self._send_btn)

        chat_layout.addWidget(self.pinned_bar)
        chat_layout.addWidget(self.chat_stack, 1)
        chat_layout.addWidget(self.attachments_panel)
        chat_layout.addWidget(self.edit_bar)
        chat_layout.addWidget(self.reply_bar)
        chat_layout.addWidget(self.emoji_bar)
        chat_layout.addWidget(self.link_preview_bar)
        chat_layout.addWidget(composer)

        content_layout.addWidget(self.user_panel)
        content_layout.addWidget(chat_panel, 1)

        root.addWidget(topbar)
        root.addWidget(self._header_label)
        root.addWidget(meta_bar)
        root.addWidget(content_frame, 1)

        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.status_label = QLabel("")
        self.status.addWidget(self.status_label)
        self.setStatusBar(self.status)

        self._render_user_list()
        self._update_maximize_icon()
        self._apply_chat_background_from_config()

    def apply_translations(self) -> None:
        self._title_label.setText(t("app.short_title"))
        self._header_label.setText(t("app.org_name"))
        self._settings_btn.setToolTip(t("settings.title"))
        self._minimize_btn.setToolTip(t("window.minimize"))
        self._close_btn.setToolTip(t("common.close"))
        self.pinned_clear_btn.setToolTip(t("pin.clear_tooltip"))
        self.search_input.setPlaceholderText(t("search.placeholder"))
        self._user_title.setText(t("user.list_title"))
        self._attach_btn.setToolTip(t("composer.attach"))
        self.text_input.setPlaceholderText(t("composer.placeholder"))
        self._send_btn.setText(t("composer.send"))
        self.lp_close_btn.setToolTip(t("linkpreview.close"))
        self._update_maximize_icon()

        count = len([p for p in self._peers if p.get("sender_id") != self._store.config.sender_id]) + 1
        self.online_label.setText(t("status.online_count", count=count))

        if self._pinned_message:
            preview = self._pinned_message.get("preview") or ""
            name = self._pinned_message.get("name") or ""
            label = t("pin.label_default", preview=preview)
            if name:
                label = t("pin.label_named", name=name, preview=preview)
            self.pinned_label.setText(label)

        if self._reply_target:
            preview = _trim_text(self._reply_target.get("text") or self._reply_target.get("filename") or "")
            name = self._reply_target.get("name") or t("user.unknown")
            self.reply_label.setText(t("reply.label", name=name, preview=preview))

        if self._edit_target:
            preview = _trim_text(self._edit_target.get("text") or "")
            self.edit_label.setText(t("edit.label", preview=preview))

        if self.link_preview_bar.isVisible():
            if self._lp_data:
                self._render_link_preview_bar(self._lp_data)
            elif self._lp_current_url:
                self._set_link_preview_loading(self._lp_current_url)

        self._refresh_attachments()
        self._render_user_list()
        for bubble in self._message_bubbles.values():
            bubble.apply_translations()

    def resizeEvent(self, event):  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self._store_normal_geometry()
        self._update_bubble_widths()
        self._update_chat_background_geometry()

    def moveEvent(self, event):  # noqa: N802 - Qt naming
        super().moveEvent(event)
        self._store_normal_geometry()

    def _store_normal_geometry(self) -> None:
        if self.windowState() & (Qt.WindowMaximized | Qt.WindowMinimized):
            return
        self._normal_geometry = self.geometry()

    def _apply_pending_geometry(self) -> None:
        if not self._pending_normal_geometry:
            return
        if self.windowState() & (Qt.WindowMaximized | Qt.WindowMinimized):
            self._pending_geometry_attempts += 1
            if self._pending_geometry_attempts <= 6:
                QTimer.singleShot(0, self._apply_pending_geometry)
            return
        self._pending_geometry_attempts = 0
        self.setGeometry(self._pending_normal_geometry)
        self._pending_normal_geometry = None

    def _update_bubble_widths(self) -> None:
        target = int(self.chat_area.viewport().width() * 0.62)
        target = max(360, min(720, target))
        for idx in range(self.chat_layout.count()):
            item = self.chat_layout.itemAt(idx)
            widget = item.widget() if item else None
            if isinstance(widget, ChatBubble):
                bubbles = [widget]
            elif widget is not None:
                bubbles = widget.findChildren(ChatBubble)
            else:
                bubbles = []
            for bubble in bubbles:
                bubble.setFixedWidth(target)
                bubble.updateGeometry()

    def _apply_chat_background_from_config(self) -> None:
        mode = self._store.config.chat_bg_mode or "off"
        opacity = int(self._store.config.chat_bg_opacity or 0)
        opacity = max(0, min(100, opacity))
        colors = theme_mod.get_bubble_colors(self._store.config.theme)
        surface = colors.get("chat_surface", "#0F1412")

        if mode == "color":
            color = QColor(self._store.config.chat_bg_color or surface)
            if not color.isValid():
                color = QColor(surface)
            alpha = int(255 * (opacity / 100.0))
            self._chat_bg_color.setStyleSheet(
                f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {alpha});"
            )
            self._chat_bg_color.show()
            self._chat_bg_image.hide()
        elif mode == "image":
            path = self._store.config.chat_bg_image_path or ""
            pixmap = QPixmap(path) if path else QPixmap()
            if not pixmap.isNull():
                self._chat_bg_path = path
                self._chat_bg_pixmap = pixmap
                self._chat_bg_image_fx.setOpacity(opacity / 100.0)
                self._chat_bg_image.show()
                self._chat_bg_color.hide()
                self._update_chat_background_geometry()
            else:
                self._chat_bg_image.hide()
                self._chat_bg_color.setStyleSheet(f"background-color: {surface};")
                self._chat_bg_color.show()
        else:
            self._chat_bg_image.hide()
            self._chat_bg_color.setStyleSheet(f"background-color: {surface};")
            self._chat_bg_color.show()

    def _update_chat_background_geometry(self) -> None:
        if not self._chat_bg_image.isVisible() or self._chat_bg_pixmap is None:
            return
        size = self.chat_stack.size()
        if size.width() <= 0 or size.height() <= 0:
            return
        scaled = self._chat_bg_pixmap.scaled(
            size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        self._chat_bg_image.setPixmap(scaled)

    def set_online_count(self, count: int) -> None:
        self.online_label.setText(t("status.online_count", count=count))

    def set_peers(self, peers: list[dict[str, Any]]) -> None:
        self._peers = peers
        other_peers = [p for p in peers if p.get("sender_id") != self._store.config.sender_id]
        self.online_label.setText(t("status.online_count", count=len(other_peers) + 1))
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
        avatar_size = 46
        colors = theme_mod.get_bubble_colors(self._store.config.theme)
        avatar_border = QColor(colors.get("avatar_border", colors.get("bubble_border", "#1B2B22")))
        avatar_pix = load_avatar_pixmap(
            self._store.config.avatar_path if is_self else "",
            msg.get("name") or "",
            msg.get("avatar_sha256") or "",
            avatar_size,
            avatar_border,
            1,
        )
        avatar_lbl = QLabel()
        avatar_lbl.setObjectName("chatAvatar")
        avatar_lbl.setProperty("sender_id", msg.get("sender_id") or "")
        avatar_lbl.setProperty("sender_name", msg.get("name") or "")
        avatar_lbl.setProperty("is_self", bool(is_self))
        avatar_lbl.setFixedSize(avatar_size, avatar_size)
        avatar_lbl.setPixmap(avatar_pix)
        avatar_lbl.setScaledContents(True)
        avatar_lbl.setStyleSheet("background: transparent;")

        bubble = ChatBubble(msg, is_self, self._store.config.theme)
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

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)
        if is_self:
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignBottom)
            row_layout.addWidget(avatar_lbl, 0, Qt.AlignBottom)
        else:
            row_layout.addWidget(avatar_lbl, 0, Qt.AlignBottom)
            row_layout.addWidget(bubble, 0, Qt.AlignBottom)
            row_layout.addStretch(1)
        self.chat_layout.addWidget(row)
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
        label = t("pin.label_default", preview=preview)
        if name:
            label = t("pin.label_named", name=name, preview=preview)
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
        colors = theme_mod.get_bubble_colors(self._store.config.theme)
        avatar_border = QColor(colors.get("avatar_border", colors.get("bubble_border", "#1B2B22")))
        for idx in range(self.chat_layout.count()):
            item = self.chat_layout.itemAt(idx)
            row = item.widget() if item else None
            if not isinstance(row, QWidget):
                continue
            for avatar_lbl in row.findChildren(QLabel, "chatAvatar"):
                if avatar_lbl.property("sender_id") != sender_id:
                    continue
                name = avatar_lbl.property("sender_name") or ""
                is_self = bool(avatar_lbl.property("is_self"))
                avatar_path = self._store.config.avatar_path if is_self else ""
                size = avatar_lbl.width() or 46
                pixmap = load_avatar_pixmap(avatar_path, name, avatar_sha, size, avatar_border, 1)
                avatar_lbl.setPixmap(pixmap)
        item = self._user_items.get(sender_id)
        if item:
            name = item.raw_name()
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
        self._update_link_preview_from_composer()

    def _set_typing(self, state: bool) -> None:
        if state == self._typing_state:
            return
        self._typing_state = state
        self.typing_changed.emit(state)
        self._render_user_list()

    def _update_link_preview_from_composer(self) -> None:
        if not hasattr(self, "text_input"):
            return
        text = self.text_input.toPlainText()
        url = extract_first_url(text)
        if not url:
            self._reset_link_preview_state(clear_dismissed=True)
            return
        url = _normalize_preview_url(url)
        if self._lp_current_url != url:
            self._lp_current_url = url
            if self._lp_dismissed_url and self._lp_dismissed_url != url:
                self._lp_dismissed_url = None
            self._lp_failed_url = None
            self._lp_data = None
            self._lp_thumb_path = None
            self._lp_thumb_file_id = None
            self._lp_thumb_url = None
            self._lp_thumb_error = None
            self._set_link_preview_loading(url)
            self._start_link_preview_fetch(url)
            return
        if url == self._lp_dismissed_url or url == self._lp_failed_url:
            self.link_preview_bar.hide()
            return
        if self._lp_data:
            self._render_link_preview_bar(self._lp_data)
            return
        if self._lp_worker and self._lp_worker.isRunning():
            self._set_link_preview_loading(url)
            return
        self._set_link_preview_loading(url)
        self._start_link_preview_fetch(url)

    def _start_link_preview_fetch(self, url: str) -> None:
        worker = LinkPreviewWorker(url)
        self._lp_worker = worker
        self._lp_workers.append(worker)
        worker.finished.connect(self._on_link_preview_ready)
        worker.failed.connect(self._on_link_preview_failed)
        worker.finished.connect(self._cleanup_link_preview_workers)
        worker.failed.connect(self._cleanup_link_preview_workers)
        worker.start()

    def _dismiss_link_preview(self) -> None:
        if self._lp_current_url:
            self._lp_dismissed_url = self._lp_current_url
        self.link_preview_bar.hide()

    def _reset_link_preview_state(self, clear_dismissed: bool = False) -> None:
        self._lp_current_url = None
        self._lp_data = None
        self._lp_thumb_path = None
        self._lp_thumb_file_id = None
        self._lp_thumb_url = None
        self._lp_thumb_error = None
        self._lp_failed_url = None
        if clear_dismissed:
            self._lp_dismissed_url = None
        self.lp_domain_label.setText("")
        self.lp_title_label.setText("")
        self.lp_desc_label.setText("")
        self.lp_desc_label.show()
        self.lp_thumb_label.hide()
        self.lp_thumb_label.clear()
        self.lp_thumb_label.setToolTip("")
        self.link_preview_bar.hide()

    def _set_link_preview_loading(self, url: str) -> None:
        self.link_preview_bar.show()
        self.lp_domain_label.setText(_display_url(url))
        self.lp_title_label.setText(t("linkpreview.loading"))
        self.lp_desc_label.setText("")
        self.lp_desc_label.hide()
        self.lp_thumb_label.hide()
        self.lp_thumb_label.clear()

    def _render_link_preview_bar(self, data: dict) -> None:
        url = data.get("url") or self._lp_current_url or ""
        domain = data.get("site_name") or data.get("display_url") or _display_url(url)
        title = data.get("title") or data.get("display_url") or url
        desc = data.get("description") or ""
        self.lp_domain_label.setText(domain)
        self.lp_title_label.setText(title)
        self.lp_desc_label.setText(desc)
        self.lp_desc_label.setVisible(bool(desc))
        if self._lp_thumb_path and Path(self._lp_thumb_path).exists():
            self._set_link_preview_thumb(self._lp_thumb_path)
        else:
            if self._lp_thumb_error:
                self._set_link_preview_thumb_error(self._lp_thumb_error)
            else:
                self.lp_thumb_label.hide()
                self.lp_thumb_label.clear()
                self.lp_thumb_label.setToolTip("")
        self.link_preview_bar.show()

    def _set_link_preview_thumb(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        _set_cover_pixmap(self.lp_thumb_label, pixmap)
        self.lp_thumb_label.setText("")
        self.lp_thumb_label.setToolTip("")
        self.lp_thumb_label.show()

    def _set_link_preview_thumb_loading(self) -> None:
        self.lp_thumb_label.setText(t("linkpreview.thumb_loading"))
        self.lp_thumb_label.setAlignment(Qt.AlignCenter)
        self.lp_thumb_label.setToolTip(t("linkpreview.loading_image"))
        self.lp_thumb_label.show()

    def _set_link_preview_thumb_error(self, reason: str) -> None:
        message = (
            t("linkpreview.thumbnail_unavailable_reason", reason=reason)
            if reason
            else t("linkpreview.thumbnail_unavailable")
        )
        self.lp_thumb_label.setText("!")
        self.lp_thumb_label.setAlignment(Qt.AlignCenter)
        self.lp_thumb_label.setToolTip(message)
        self.lp_thumb_label.show()

    def _on_link_preview_ready(self, url: str, data: dict) -> None:
        if url != self._lp_current_url:
            return
        self._lp_data = data
        title_len = len(data.get("title") or "")
        desc_len = len(data.get("description") or "")
        image_url = (data.get("image_url") or "").strip()
        encoding = data.get("_encoding") or ""
        if title_len == 0 or desc_len == 0 or not image_url or _is_favicon_url(image_url):
            _log_link_preview(
                f"linkpreview_meta url={data.get('url') or url} title={title_len} desc={desc_len} "
                f"image={image_url or ''} enc={encoding}"
            )
        if url == self._lp_dismissed_url:
            return
        self._render_link_preview_bar(data)
        image_url = data.get("image_url") or ""
        if not image_url:
            return
        file_id = _link_thumb_file_id(data.get("url") or self._lp_current_url or url)
        self._lp_thumb_file_id = file_id
        cached_path = attachment_cache_path(file_id, "thumb.jpg")
        if _is_thumb_cache_valid(file_id, image_url):
            _log_thumb_cache(file_id, reused=True, src_changed=False)
            self._lp_thumb_path = str(cached_path)
            self._set_link_preview_thumb(str(cached_path))
            return
        if cached_path.exists():
            _log_thumb_cache(file_id, reused=False, src_changed=True)
        else:
            _log_thumb_cache(file_id, reused=False, src_changed=False)
        self._set_link_preview_thumb_loading()
        self._start_link_thumb_fetch(image_url, data.get("url") or self._lp_current_url or url, file_id)

    def _on_link_preview_failed(self, url: str, _err: str) -> None:
        if url != self._lp_current_url:
            return
        _log_link_preview(f"linkpreview_meta url={url} title=0 desc=0 image=no")
        self._lp_failed_url = url
        self._lp_data = None
        self._lp_thumb_path = None
        self._lp_thumb_file_id = None
        self._lp_thumb_url = None
        self.link_preview_bar.hide()

    def _start_link_thumb_fetch(self, image_url: str, page_url: str, file_id: str) -> None:
        worker = LinkThumbWorker(image_url, page_url, file_id)
        self._lp_thumb_worker = worker
        self._lp_thumb_workers.append(worker)
        worker.finished.connect(self._on_link_thumb_ready)
        worker.failed.connect(self._on_link_thumb_failed)
        worker.finished.connect(self._cleanup_link_thumb_workers)
        worker.failed.connect(self._cleanup_link_thumb_workers)
        worker.start()

    def _on_link_thumb_ready(self, page_url: str, file_id: str, thumb_path: str) -> None:
        if file_id != self._lp_thumb_file_id:
            return
        self._lp_thumb_path = thumb_path
        self._lp_thumb_error = None
        self._set_link_preview_thumb(thumb_path)

    def _on_link_thumb_failed(self, page_url: str, err: str) -> None:
        current_urls = {self._lp_current_url or "", (self._lp_data or {}).get("url") or ""}
        if page_url and page_url not in current_urls:
            return
        if not self._lp_thumb_file_id:
            return
        self._lp_thumb_path = None
        self._lp_thumb_error = err
        self._set_link_preview_thumb_error(err)
        _log_link_preview(f"linkpreview_thumb_fail url={page_url} reason={err}")

    def _cleanup_link_preview_workers(self) -> None:
        self._lp_workers = [w for w in self._lp_workers if w.isRunning()]
        if self._lp_worker and not self._lp_worker.isRunning():
            self._lp_worker = None

    def _cleanup_link_thumb_workers(self) -> None:
        self._lp_thumb_workers = [w for w in self._lp_thumb_workers if w.isRunning()]
        if self._lp_thumb_worker and not self._lp_thumb_worker.isRunning():
            self._lp_thumb_worker = None

    def _set_reply(self, msg: dict) -> None:
        self._clear_edit()
        self._reply_target = msg
        preview = msg.get("text") or msg.get("filename") or ""
        preview = _trim_text(preview)
        name = msg.get("name") or t("user.unknown")
        self.reply_label.setText(t("reply.label", name=name, preview=preview))
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
        self.edit_label.setText(t("edit.label", preview=preview))
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
                self.show_status(t("status.edit_too_long"))
                return
            if target_id and text:
                self.apply_edit(target_id, text)
                self.edit_message.emit(target_id, text)
            else:
                self.show_status(t("status.edit_missing_text"))
            self.text_input.clear()
            self._clear_edit()
            self._set_typing(False)
            return
        send_text = False
        if text:
            if len(text.encode("utf-8")) > protocol.MAX_TEXT_BYTES:
                self.show_status(t("status.message_too_long"))
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
            if (
                self._lp_data
                and self._lp_current_url
                and self._lp_current_url != self._lp_dismissed_url
            ):
                preview_url = self._lp_data.get("url") or self._lp_current_url
                payload["link_preview"] = {
                    "url": preview_url,
                    "display_url": self._lp_data.get("display_url") or _display_url(preview_url),
                    "title": self._lp_data.get("title") or "",
                    "description": self._lp_data.get("description") or "",
                    "site_name": self._lp_data.get("site_name") or "",
                }
                if self._lp_thumb_path and self._lp_thumb_file_id:
                    payload["link_preview"]["thumb_path"] = self._lp_thumb_path
                    payload["link_preview"]["thumb_file_id"] = self._lp_thumb_file_id
            self.send_text.emit(payload)
            self.text_input.clear()
            self._clear_reply()
            self._set_typing(False)
            self._reset_link_preview_state(clear_dismissed=True)

        if self._attachments:
            self.send_files.emit(list(self._attachments))
            self._attachments = []
            self._refresh_attachments()

    def _choose_files(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        files, _ = QFileDialog.getOpenFileNames(self, t("file.choose_files_title"))
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
            label = QLabel(
                t("attachments.label", name=Path(path).name, size=_format_size(size))
            )
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
            elif isinstance(widget, QWidget):
                bubble = widget.findChild(ChatBubble)
                if bubble:
                    widget.setVisible(bubble.matches_filter(query))

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
            self.show_status(t("pin.not_found"))

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

    def _is_in_titlebar(self, global_pos: QPoint) -> bool:
        topbar = getattr(self, "_topbar", None)
        if not topbar or not topbar.isVisible():
            return False
        if not topbar.rect().contains(topbar.mapFromGlobal(global_pos)):
            return False
        for widget in getattr(self, "_title_controls", set()):
            if widget.isVisible() and widget.rect().contains(widget.mapFromGlobal(global_pos)):
                return False
        return True

    def _hit_test_edges(self, global_pos: QPoint) -> Qt.Edges:
        if self.windowState() & Qt.WindowMaximized:
            return Qt.Edges()
        pos = self.mapFromGlobal(global_pos)
        rect = self.rect()
        margin = max(1, int(getattr(self, "_resize_margin", 6)))
        edges = Qt.Edges()
        if pos.x() <= margin:
            edges |= Qt.LeftEdge
        elif pos.x() >= rect.width() - margin:
            edges |= Qt.RightEdge
        if pos.y() <= margin:
            edges |= Qt.TopEdge
        elif pos.y() >= rect.height() - margin:
            edges |= Qt.BottomEdge
        return edges

    def _update_resize_cursor(self, edges: Qt.Edges) -> None:
        if edges == self._resize_edges:
            return
        self._resize_edges = edges
        if not edges:
            self.unsetCursor()
            return
        if edges in (Qt.LeftEdge | Qt.TopEdge, Qt.RightEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edges in (Qt.RightEdge | Qt.TopEdge, Qt.LeftEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edges in (Qt.LeftEdge, Qt.RightEdge):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.SizeVerCursor)

    def nativeEvent(self, eventType, message):  # noqa: N802 - Qt naming
        if not getattr(self, "_use_native_frame", False):
            return super().nativeEvent(eventType, message)
        if eventType not in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            return super().nativeEvent(eventType, message)

        WM_NCHITTEST = 0x0084
        HTCLIENT = 1
        HTCAPTION = 2
        HTLEFT = 10
        HTRIGHT = 11
        HTTOP = 12
        HTTOPLEFT = 13
        HTTOPRIGHT = 14
        HTBOTTOM = 15
        HTBOTTOMLEFT = 16
        HTBOTTOMRIGHT = 17

        if ctypes.sizeof(ctypes.c_void_p) == 8:
            wparam_t = ctypes.c_uint64
            lparam_t = ctypes.c_int64
        else:
            wparam_t = ctypes.c_uint32
            lparam_t = ctypes.c_int32

        class _POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class _MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", ctypes.c_void_p),
                ("message", ctypes.c_uint),
                ("wParam", wparam_t),
                ("lParam", lparam_t),
                ("time", ctypes.c_uint32),
                ("pt", _POINT),
            ]

        msg = _MSG.from_address(int(message))
        if msg.message != WM_NCHITTEST:
            return super().nativeEvent(eventType, message)

        x = ctypes.c_short(msg.lParam & 0xFFFF).value
        y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
        global_pos = QPoint(x, y)

        if not self.isVisible():
            return super().nativeEvent(eventType, message)

        if self.windowState() & Qt.WindowMaximized:
            if self._is_in_titlebar(global_pos):
                return True, HTCAPTION
            return True, HTCLIENT

        pos = self.mapFromGlobal(global_pos)
        rect = self.rect()
        margin = max(1, int(getattr(self, "_resize_margin", 6)))
        left = pos.x() <= margin
        right = pos.x() >= rect.width() - margin
        top = pos.y() <= margin
        bottom = pos.y() >= rect.height() - margin

        if left and top:
            return True, HTTOPLEFT
        if right and top:
            return True, HTTOPRIGHT
        if left and bottom:
            return True, HTBOTTOMLEFT
        if right and bottom:
            return True, HTBOTTOMRIGHT
        if top:
            return True, HTTOP
        if bottom:
            return True, HTBOTTOM
        if left:
            return True, HTLEFT
        if right:
            return True, HTRIGHT

        if self._is_in_titlebar(global_pos):
            return True, HTCAPTION
        return True, HTCLIENT

    def eventFilter(self, obj, event):  # noqa: N802 - Qt naming
        if isinstance(obj, QWidget) and obj.window() is self:
            if event.type() == QEvent.MouseMove and not (event.buttons() & Qt.LeftButton):
                edges = self._hit_test_edges(event.globalPosition().toPoint())
                self._update_resize_cursor(edges)
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                edges = self._hit_test_edges(event.globalPosition().toPoint())
                if edges:
                    window = self.windowHandle()
                    if window and hasattr(window, "startSystemResize"):
                        if window.startSystemResize(edges):
                            return True
        if obj in getattr(self, "_drag_widgets", set()):
            if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self._drag_active = False
                self._toggle_maximize()
                return True
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                edges = self._hit_test_edges(event.globalPosition().toPoint())
                if edges:
                    window = self.windowHandle()
                    if window and hasattr(window, "startSystemResize"):
                        if window.startSystemResize(edges):
                            return True
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

    def changeEvent(self, event):  # noqa: N802 - Qt naming
        if event.type() == QEvent.WindowStateChange:
            self._apply_pending_geometry()
            self._update_maximize_icon()
        super().changeEvent(event)

    def _toggle_maximize(self) -> None:
        if self.windowState() & Qt.WindowMaximized:
            normal = self.normalGeometry()
            target = None
            if normal.isValid() and normal.width() > 0 and normal.height() > 0:
                target = normal
            elif self._normal_geometry is not None:
                target = self._normal_geometry
            self._pending_normal_geometry = target
            self.showNormal()
            QTimer.singleShot(0, self._apply_pending_geometry)
        else:
            self._store_normal_geometry()
            self.showMaximized()
        self._update_maximize_icon()

    def _update_maximize_icon(self) -> None:
        if not hasattr(self, "_max_btn"):
            return
        style = self.style()
        if self.windowState() & Qt.WindowMaximized:
            self._max_btn.setIcon(style.standardIcon(QStyle.SP_TitleBarNormalButton))
            self._max_btn.setToolTip(t("window.restore"))
        else:
            self._max_btn.setIcon(style.standardIcon(QStyle.SP_TitleBarMaxButton))
            self._max_btn.setToolTip(t("window.maximize"))

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
            self.show_status(t("download.no_url"))
            return
        parsed = urllib.parse.urlparse(url)
        if not parsed.netloc:
            url = f"http://{sender_ip}{parsed.path}"
        filename = msg.get("filename") or "download.bin"
        file_id = msg.get("file_id") or ""

        from PySide6.QtWidgets import QFileDialog
        dest_dir = downloads_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)
        suggested = dest_dir / filename
        dest_file, _ = QFileDialog.getSaveFileName(
            self,
            t("file.save_title"),
            str(suggested),
            t("file.all_files_filter"),
        )
        if not dest_file:
            return
        dest_path = Path(dest_file)

        bubble = self._file_bubbles.get(file_id) if file_id else None
        cached_path = attachment_cache_path(file_id, filename) if file_id else None
        if cached_path and cached_path.exists():
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil

                shutil.copy2(cached_path, dest_path)
                if bubble:
                    bubble.set_download_status("download.saved")
                if _is_image_file(filename):
                    bubble.set_image_preview(str(cached_path))
                self.status_label.setText(t("download.saved_label", name=filename))
                return
            except Exception:
                pass

        if bubble:
            bubble.set_download_status("download.loading")
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
        self.status_label.setText(t("download.loading_label", name=name, percent=pct))

    def _finish_download(self, bubble: ChatBubble | None, name: str, path: str, filename: str) -> None:
        if bubble:
            bubble.set_download_status("download.saved")
            bubble.set_download_progress(100)
            if _is_image_file(filename):
                bubble.set_image_preview(path)
        self.status_label.setText(t("download.finished_label", name=name))

    def _fail_download(self, bubble: ChatBubble | None, name: str) -> None:
        if bubble:
            bubble.set_download_status("download.error")
        self.status_label.setText(t("download.error_label", name=name))

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


_LINKPREVIEW_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)
_FACEBOOK_UA = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"

_LINKPREVIEW_HTML_HEADERS = {
    "User-Agent": _LINKPREVIEW_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "identity",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

_LINKPREVIEW_IMAGE_HEADERS = {
    "User-Agent": _LINKPREVIEW_UA,
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Encoding": "identity",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").split())


def _first_meta_value(meta: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = meta.get(key.lower()) or ""
        if value.strip():
            return value.strip()
    return ""


def _log_link_preview(message: str) -> None:
    if not message:
        return
    try:
        path = logs_dir() / "link_preview.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{message}\n")
    except Exception:
        pass


def _log_thumb_cache(file_id: str, reused: bool, src_changed: bool) -> None:
    _log_link_preview(
        f"linkpreview_thumb_cache file_id={file_id} reused={'yes' if reused else 'no'} "
        f"src_changed={'yes' if src_changed else 'no'}"
    )


def _thumb_src_path(file_id: str) -> Path:
    return attachment_cache_path(file_id, "thumb_src.txt")


def _read_thumb_src(file_id: str) -> str:
    path = _thumb_src_path(file_id)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _write_thumb_src(file_id: str, src: str) -> None:
    if not file_id:
        return
    path = _thumb_src_path(file_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(src or "", encoding="utf-8")
    except Exception:
        pass


def _is_thumb_cache_valid(file_id: str, source_url: str) -> bool:
    if not file_id or not source_url:
        return False
    cache_path = attachment_cache_path(file_id, "thumb.jpg")
    if not cache_path.exists():
        return False
    cached_src = _read_thumb_src(file_id)
    return bool(cached_src) and cached_src == source_url


def _resolve_url(base_url: str, url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if base_url:
        return urllib.parse.urljoin(base_url, url)
    return url


def _is_favicon_url(url: str) -> bool:
    url = (url or "").lower()
    return "favicon.ico" in url or url.endswith("/favicon.ico")


def _pick_image_url(
    meta: dict[str, str],
    parser: _LinkPreviewHTMLParser,
    base_url: str,
    canonical_url: str,
    target_url: str,
) -> tuple[str, str, bool]:
    for key in ["og:image", "og:image:secure_url", "og:image:url"]:
        value = meta.get(key)
        if value:
            return _resolve_url(base_url, value), "og", True
    for key in ["twitter:image", "twitter:image:src"]:
        value = meta.get(key)
        if value:
            return _resolve_url(base_url, value), "twitter", True
    if parser.link_image_src:
        return _resolve_url(base_url, parser.link_image_src), "image_src", True
    value = meta.get("image")
    if value:
        return _resolve_url(base_url, value), "image_src", True
    if parser.link_apple_icon:
        return _resolve_url(base_url, parser.link_apple_icon), "icon", False
    if parser.link_icon:
        return _resolve_url(base_url, parser.link_icon), "icon", False
    host = _display_url(canonical_url or target_url)
    if host:
        return f"https://{host}/favicon.ico", "favicon", False
    return "", "", False


def _is_facebook_host(url: str) -> bool:
    host = (urllib.parse.urlparse(url or "").netloc or "").lower()
    return host.endswith("facebook.com") or host.endswith("fb.watch")


def _fetch_youtube_oembed(url: str) -> dict[str, str] | None:
    if not url:
        return None
    try:
        endpoint = "https://www.youtube.com/oembed?format=json&url="
        req_url = endpoint + urllib.parse.quote(url, safe="")
        req = urllib.request.Request(req_url, headers=_LINKPREVIEW_HTML_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return None
            raw = resp.read()
        data = json.loads(raw.decode("utf-8", errors="replace"))
        if not isinstance(data, dict):
            return None
        return {
            "title": str(data.get("title") or ""),
            "thumbnail_url": str(data.get("thumbnail_url") or ""),
        }
    except Exception:
        return None


def _extract_youtube_id(url: str) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""
    if "youtu.be" in host:
        return path.strip("/").split("/")[0]
    if "youtube.com" not in host:
        return ""
    query = urllib.parse.parse_qs(parsed.query or "")
    if "v" in query and query["v"]:
        return query["v"][0]
    parts = [p for p in path.split("/") if p]
    if parts:
        if parts[0] in {"embed", "shorts", "v"} and len(parts) > 1:
            return parts[1]
    return ""


def _normalize_preview_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("<") and url.endswith(">") and len(url) > 2:
        url = url[1:-1].strip()
    if url.startswith("www."):
        return f"https://{url}"
    if url.startswith("http://www."):
        return "https://" + url[len("http://") :]
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme:
        return f"https://{url}"
    return url


def _display_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc or parsed.path
    if "/" in host:
        host = host.split("/", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def _link_thumb_file_id(url: str) -> str:
    digest = hashlib.sha1((url or "").encode("utf-8")).hexdigest()
    return f"lp_{digest[:12]}"


def _set_cover_pixmap(label: QLabel, pixmap: QPixmap) -> None:
    size = label.size()
    if size.width() <= 0 or size.height() <= 0:
        return
    scaled = pixmap.scaled(size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = max(0, (scaled.width() - size.width()) // 2)
    y = max(0, (scaled.height() - size.height()) // 2)
    label.setPixmap(scaled.copy(x, y, size.width(), size.height()))


def _resize_cover_image(image, target_w: int, target_h: int):
    w, h = image.size
    if w <= 0 or h <= 0:
        return image
    scale = max(target_w / w, target_h / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    from PIL import Image

    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    resized = image.resize((new_w, new_h), resample=resample)
    left = max(0, (new_w - target_w) // 2)
    top = max(0, (new_h - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def create_link_thumb(image_url: str, page_url: str, file_id: str) -> tuple[str | None, str | None]:
    if not image_url or not file_id:
        return None, "missing input"
    cache_path = attachment_cache_path(file_id, "thumb.jpg")
    cached_src = _read_thumb_src(file_id)
    if cache_path.exists() and cached_src == image_url:
        return str(cache_path), None
    try:
        headers = dict(_LINKPREVIEW_IMAGE_HEADERS)
        if page_url:
            headers["Referer"] = page_url
        if _is_facebook_host(page_url or image_url):
            headers["User-Agent"] = _FACEBOOK_UA
        req = urllib.request.Request(image_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "text/html" in content_type:
                return None, "html response"
            if "svg" in content_type or "xml" in content_type:
                return None, "svg unsupported"
            max_bytes = 3 * 1024 * 1024
            data = bytearray()
            while len(data) < max_bytes:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) >= max_bytes:
                    return None, "image too large"
        if not data:
            return None, "empty image response"
        try:
            from PIL import Image
        except Exception as exc:  # pragma: no cover - pillow missing
            return None, f"pillow missing: {exc}"
        image = Image.open(io.BytesIO(data))
        if image.format == "GIF":
            try:
                image.seek(0)
            except Exception:
                pass
        image = image.convert("RGB")
        image = _resize_cover_image(image, 240, 240)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(cache_path), format="JPEG", quality=75)
        _write_thumb_src(file_id, image_url)
        return str(cache_path), None
    except Exception as exc:
        return None, str(exc)
