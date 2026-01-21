from __future__ import annotations

from PySide6.QtWidgets import QApplication


NEON_GREEN = "#39FF14"
BG_BASE = "#0A0D0B"
BG_DARKER = "#050605"
SURFACE = "#0F1412"
PANEL = "#101815"
BORDER = "#1C2A22"
TEXT = "#E6FFE0"
TEXT_MUTED = "#8FB39A"


THEME_QSS = f"""
QMainWindow {{
    background: qradialgradient(cx:0.15, cy:0.1, radius:1.1, fx:0.1, fy:0.1, stop:0 #0F1512, stop:1 {BG_DARKER});
    color: {TEXT};
}}
QDialog {{
    background: {BG_BASE};
    color: {TEXT};
}}
QWidget {{
    background: transparent;
    color: {TEXT};
    font-family: 'Bahnschrift';
    font-size: 10pt;
}}
QWidget#appRoot {{
    background: transparent;
}}
QFrame#topBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0B0F0D, stop:1 #111815);
    border-bottom: 1px solid {BORDER};
}}
QLabel#appTitle {{
    color: {TEXT};
    font-weight: 600;
}}
QLabel#headerTitle {{
    color: {NEON_GREEN};
    font-family: 'Bahnschrift';
    font-size: 20pt;
}}
QLabel#onlineLabel {{
    color: {TEXT_MUTED};
    font-size: 9pt;
}}
QFrame#chatCanvas {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#composerBar {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#attachmentsPanel {{
    background: #0B0F0E;
    border: 1px dashed {BORDER};
    border-radius: 10px;
}}
QFrame#chatBubble {{
    background: #0E1411;
    border: 1px solid #1B2B22;
    border-radius: 12px;
    padding: 10px;
}}
QFrame#chatBubbleSelf {{
    background: #0E1A12;
    border-radius: 12px;
    padding: 10px;
    border: 1px solid #2C5C38;
}}
QLabel#nameLabel {{
    color: {NEON_GREEN};
    font-weight: 600;
}}
QLabel#timeLabel {{
    color: {TEXT_MUTED};
    font-size: 8pt;
}}
QLabel#chatText {{
    color: {TEXT};
}}
QLabel#chatText a {{
    color: {NEON_GREEN};
}}
QLabel#avatarPreview {{
    background: #0B0F0E;
    border: 1px solid {BORDER};
    border-radius: 36px;
}}
QLabel#aboutBox {{
    background: #0B0F0E;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px;
}}
QFrame#fileCard {{
    background: #0B0F0E;
    border: 1px solid #1E3326;
    border-radius: 8px;
}}
QLabel#fileLabel {{
    color: {TEXT};
}}
QLineEdit, QTextEdit {{
    background: #0B0F0E;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
    selection-background-color: #1E3D2A;
}}
QPushButton {{
    background: #0B0F0E;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
}}
QPushButton:hover {{
    border-color: {NEON_GREEN};
}}
QPushButton#primaryButton {{
    background: {NEON_GREEN};
    color: #041007;
    border: 1px solid {NEON_GREEN};
    font-weight: 600;
}}
QPushButton#primaryButton:hover {{
    background: #6BFF47;
}}
QPushButton#iconButton {{
    background: #0B0F0E;
    border: 1px solid {BORDER};
}}
QPushButton#downloadButton {{
    border: 1px solid {NEON_GREEN};
}}
QToolButton {{
    background: #0B0F0E;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
}}
QToolButton:hover {{
    border-color: {NEON_GREEN};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollArea::viewport {{
    background: transparent;
}}
QScrollBar:vertical {{
    width: 10px;
    background: #0B0F0E;
}}
QScrollBar::handle:vertical {{
    background: #1D4021;
    border-radius: 4px;
}}
QStatusBar {{
    background: #0B0F0E;
    color: {TEXT_MUTED};
}}
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER};
    background: #0B0F0E;
}}
QCheckBox::indicator:checked {{
    background: {NEON_GREEN};
    border: 1px solid {NEON_GREEN};
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(THEME_QSS)
