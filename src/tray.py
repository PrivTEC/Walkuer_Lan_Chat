from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from util.i18n import t


class TrayManager(QObject):
    def __init__(self, icon: QIcon, parent, on_open, on_settings, on_about, on_quit) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(icon, parent)
        self._tray.setToolTip(t("tray.tooltip"))
        self._notify_queue: list[tuple[str, str]] = []
        self._notify_active = False

        menu = QMenu()
        self._open_action = QAction(t("tray.open"), menu)
        self._settings_action = QAction(t("tray.settings"), menu)
        self._about_action = QAction(t("tray.about"), menu)
        self._quit_action = QAction(t("tray.quit"), menu)

        self._open_action.triggered.connect(on_open)
        self._settings_action.triggered.connect(on_settings)
        self._about_action.triggered.connect(on_about)
        self._quit_action.triggered.connect(on_quit)

        menu.addAction(self._open_action)
        menu.addAction(self._settings_action)
        menu.addAction(self._about_action)
        menu.addSeparator()
        menu.addAction(self._quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._on_open = on_open
        self._tray.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._on_open()

    def show_message(self, title: str, message: str) -> None:
        self._notify_queue.append((title, message))
        self._process_queue()

    def _process_queue(self) -> None:
        if self._notify_active or not self._notify_queue:
            return
        self._notify_active = True
        title, message = self._notify_queue.pop(0)
        if not self._tray.isVisible():
            self._tray.show()
            QTimer.singleShot(150, lambda: self._deliver_message(title, message))
        else:
            self._deliver_message(title, message)
        QTimer.singleShot(5200, self._finish_notify)

    def _finish_notify(self) -> None:
        self._notify_active = False
        if self._notify_queue:
            self._process_queue()

    def _deliver_message(self, title: str, message: str) -> None:
        safe_title = (title or "").strip() or t("tray.default_title")
        safe_message = (message or "").strip()
        if QSystemTrayIcon.supportsMessages():
            self._tray.showMessage(safe_title, safe_message, QSystemTrayIcon.Information, 6000)
        else:
            self._tray.setToolTip(f"{safe_title}: {safe_message}")
            app = QApplication.instance()
            if app is not None:
                QApplication.alert(self._tray.parent(), 0)

    def hide(self) -> None:
        self._tray.hide()

    def apply_translations(self) -> None:
        self._tray.setToolTip(t("tray.tooltip"))
        self._open_action.setText(t("tray.open"))
        self._settings_action.setText(t("tray.settings"))
        self._about_action.setText(t("tray.about"))
        self._quit_action.setText(t("tray.quit"))
