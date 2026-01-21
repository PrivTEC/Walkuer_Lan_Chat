from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QGraphicsDropShadowEffect, QLabel, QVBoxLayout

import app_info


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Über")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(14, 12, 14, 12)

        title = QLabel("Walkür Technology")
        title.setObjectName("headerTitle")
        title.setAlignment(Qt.AlignCenter)
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(12)
        glow.setColor(Qt.green)
        glow.setOffset(0, 0)
        title.setGraphicsEffect(glow)

        info_box = QLabel(
            """
#############################
Name: Silvan Fülle
Firma: Walkür Technology
Web: https://walkuer.tech
Git: https://github.com/PrivTEC
App: Walkür LAN Chat
Zweck: Schneller Info-Austausch im Intranet (globaler Chat + Dateitransfer)
Bedienung: Schreiben, Senden, Dateien ziehen, Tray für Hintergrundbetrieb
#############################
""".strip()
        )
        info_box.setObjectName("aboutBox")
        info_box.setAlignment(Qt.AlignCenter)
        font = QFont("Consolas", 9)
        info_box.setFont(font)

        version = QLabel(f"Version {app_info.VERSION}")
        version.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(info_box)
        layout.addWidget(version)
