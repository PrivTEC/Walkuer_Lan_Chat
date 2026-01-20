from __future__ import annotations

from PySide6.QtWidgets import QApplication


NEON_GREEN = "#39FF14"
BG_DARK = "#0A0A0A"
BG_DARKER = "#050505"
PANEL = "#121212"
TEXT = "#E6FFE0"
TEXT_MUTED = "#9BC49A"


THEME_QSS = f"""
QMainWindow {{
    background: {BG_DARK};
    color: {TEXT};
}}
QDialog {{
    background: {BG_DARK};
    color: {TEXT};
}}
QWidget {{
    background: {BG_DARK};
    color: {TEXT};
    font-family: 'Segoe UI';
    font-size: 10pt;
}}
QFrame#topBar {{
    background: {BG_DARKER};
    border-bottom: 1px solid #1E1E1E;
}}
QLabel#headerTitle {{
    color: {NEON_GREEN};
    font-family: 'Bahnschrift';
    font-size: 20pt;
}}
QFrame#chatBubble {{
    background: {PANEL};
    border-radius: 10px;
    padding: 8px;
}}
QFrame#chatBubbleSelf {{
    background: #0F1C12;
    border-radius: 10px;
    padding: 8px;
    border: 1px solid #123D1E;
}}
QLabel#nameLabel {{
    color: {NEON_GREEN};
    font-weight: 600;
}}
QLabel#timeLabel {{
    color: {TEXT_MUTED};
    font-size: 8pt;
}}
QTextBrowser {{
    background: transparent;
    border: none;
    color: {TEXT};
}}
QTextBrowser a {{
    color: {NEON_GREEN};
}}
QLineEdit, QTextEdit {{
    background: #0F0F0F;
    border: 1px solid #1E1E1E;
    border-radius: 6px;
    padding: 6px;
}}
QPushButton {{
    background: #0F0F0F;
    border: 1px solid {NEON_GREEN};
    border-radius: 6px;
    padding: 6px 10px;
}}
QPushButton:hover {{
    background: #143018;
}}
QToolButton {{
    background: transparent;
    border: 1px solid #222;
    border-radius: 4px;
    padding: 4px;
}}
QScrollArea {{
    border: none;
    background: {BG_DARK};
}}
QScrollArea::viewport {{
    background: {BG_DARK};
}}
QScrollBar:vertical {{
    width: 10px;
    background: #0F0F0F;
}}
QScrollBar::handle:vertical {{
    background: #1D4021;
    border-radius: 4px;
}}
QStatusBar {{
    background: {BG_DARKER};
    color: {TEXT_MUTED};
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(THEME_QSS)
