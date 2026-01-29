from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class TrayManager(QObject):
    def __init__(self, icon: QIcon, parent, on_open, on_settings, on_about, on_quit) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(icon, parent)
        self._tray.setToolTip("Walkür LAN Chat")
        self._notify_queue: list[tuple[str, str]] = []
        self._notify_active = False

        menu = QMenu()
        open_action = QAction("Öffnen", menu)
        settings_action = QAction("Einstellungen", menu)
        about_action = QAction("Über", menu)
        quit_action = QAction("Beenden", menu)

        open_action.triggered.connect(on_open)
        settings_action.triggered.connect(on_settings)
        about_action.triggered.connect(on_about)
        quit_action.triggered.connect(on_quit)

        menu.addAction(open_action)
        menu.addAction(settings_action)
        menu.addAction(about_action)
        menu.addSeparator()
        menu.addAction(quit_action)

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
        safe_title = (title or "").strip() or "Walkuer LAN Chat"
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
