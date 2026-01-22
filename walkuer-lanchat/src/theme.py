from __future__ import annotations

from PySide6.QtWidgets import QApplication


def _build_theme(
    accent: str,
    bg_base: str,
    bg_darker: str,
    surface: str,
    panel: str,
    border: str,
    text: str,
    text_muted: str,
    bg_gradient: str,
    topbar_start: str,
    topbar_end: str,
    input_bg: str,
    bubble_bg: str,
    bubble_border: str,
    bubble_self_bg: str,
    bubble_self_border: str,
    primary_text: str,
    accent_hover: str,
    selection_bg: str,
    file_border: str,
    scroll_handle: str,
    menu_selected: str,
) -> str:
    NEON_GREEN = accent
    BG_BASE = bg_base
    BG_DARKER = bg_darker
    SURFACE = surface
    PANEL = panel
    BORDER = border
    TEXT = text
    TEXT_MUTED = text_muted
    BG_GRADIENT = bg_gradient
    TOPBAR_START = topbar_start
    TOPBAR_END = topbar_end
    INPUT_BG = input_bg
    BUBBLE_BG = bubble_bg
    BUBBLE_BORDER = bubble_border
    BUBBLE_SELF_BG = bubble_self_bg
    BUBBLE_SELF_BORDER = bubble_self_border
    PRIMARY_TEXT = primary_text
    ACCENT_HOVER = accent_hover
    SELECTION_BG = selection_bg
    FILE_BORDER = file_border
    SCROLL_HANDLE = scroll_handle
    MENU_SELECTED = menu_selected

    return f"""
QMainWindow {{
    background: qradialgradient(cx:0.15, cy:0.1, radius:1.1, fx:0.1, fy:0.1, stop:0 {BG_GRADIENT}, stop:1 {BG_DARKER});
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
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {TOPBAR_START}, stop:1 {TOPBAR_END});
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
    background: {INPUT_BG};
    border: 1px dashed {BORDER};
    border-radius: 10px;
}}
QFrame#chatBubble {{
    background: {BUBBLE_BG};
    border: 1px solid {BUBBLE_BORDER};
    border-radius: 12px;
    padding: 10px;
}}
QFrame#chatBubble[flash="true"] {{
    border: 1px solid {NEON_GREEN};
}}
QFrame#chatBubbleSelf {{
    background: {BUBBLE_SELF_BG};
    border-radius: 12px;
    padding: 10px;
    border: 1px solid {BUBBLE_SELF_BORDER};
}}
QFrame#chatBubbleSelf[flash="true"] {{
    border: 1px solid {NEON_GREEN};
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
QLabel#chatTextMuted {{
    color: {TEXT_MUTED};
}}
QLabel#chatText a {{
    color: {NEON_GREEN};
    text-decoration: underline;
    font-weight: 600;
}}
QLabel#avatarPreview {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 36px;
}}
QLabel#aboutBox {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px;
}}
QFrame#metaBar {{
    background: transparent;
}}
QLineEdit#searchInput {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 8px;
}}
QFrame#userListPanel {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#userListTitle {{
    color: {NEON_GREEN};
    font-size: 9pt;
    letter-spacing: 1px;
}}
QFrame#userItem {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
}}
QFrame#userItemSelf {{
    background: {BUBBLE_SELF_BG};
    border: 1px solid {BUBBLE_SELF_BORDER};
    border-radius: 8px;
}}
QLabel#userName {{
    color: {TEXT};
    font-weight: 600;
}}
QLabel#userStatus {{
    color: {TEXT_MUTED};
    font-size: 8pt;
}}
QLabel#userStatusTyping {{
    color: {NEON_GREEN};
    font-size: 8pt;
}}
QFrame#replyBar {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QFrame#editBar {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QLabel#replyLabel {{
    color: {TEXT_MUTED};
}}
QLabel#editLabel {{
    color: {TEXT_MUTED};
}}
QToolButton#replyClear {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 2px 6px;
}}
QToolButton#editClear {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 2px 6px;
}}
QFrame#pinnedBar {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLabel#pinnedLabel {{
    color: {TEXT};
    font-weight: 600;
}}
QToolButton#pinnedClear {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 2px 6px;
}}
QFrame#replyBox {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QLabel#replyName {{
    color: {NEON_GREEN};
    font-size: 8pt;
}}
QLabel#replyPreview {{
    color: {TEXT_MUTED};
    font-size: 8pt;
}}
QFrame#reactionBar {{
    background: transparent;
}}
QFrame#reactionChip {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLabel#reactionText {{
    color: {TEXT};
    font-size: 8pt;
}}
QToolButton#replyButton, QToolButton#reactionButton {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 2px 6px;
    min-width: 22px;
    font-size: 9pt;
}}
QToolButton#replyButton:hover, QToolButton#reactionButton:hover {{
    border-color: {NEON_GREEN};
}}
QLabel#imagePreview {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QFrame#emojiBar {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QToolButton#emojiButton {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 2px 6px;
    font-size: 11pt;
}}
QToolButton#emojiButton:hover {{
    border-color: {NEON_GREEN};
}}
QLabel#fileStatus {{
    color: {TEXT_MUTED};
    font-size: 8pt;
}}
QFrame#fileCard {{
    background: {INPUT_BG};
    border: 1px solid {FILE_BORDER};
    border-radius: 8px;
}}
QProgressBar#fileProgress {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    height: 6px;
}}
QProgressBar#fileProgress::chunk {{
    background: {NEON_GREEN};
    border-radius: 6px;
}}
QPushButton#retryButton {{
    border: 1px solid {NEON_GREEN};
}}
QLabel#fileLabel {{
    color: {TEXT};
}}
QLineEdit, QTextEdit {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
    selection-background-color: {SELECTION_BG};
}}
QComboBox {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 8px;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {INPUT_BG};
    color: {TEXT};
    selection-background-color: {MENU_SELECTED};
    border: 1px solid {BORDER};
}}
QPushButton {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
}}
QPushButton:hover {{
    border-color: {NEON_GREEN};
}}
QPushButton#primaryButton {{
    background: {NEON_GREEN};
    color: {PRIMARY_TEXT};
    border: 1px solid {NEON_GREEN};
    font-weight: 600;
}}
QPushButton#primaryButton:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#iconButton {{
    background: {INPUT_BG};
    border: 1px solid {BORDER};
}}
QPushButton#downloadButton {{
    border: 1px solid {NEON_GREEN};
}}
QToolButton {{
    background: {INPUT_BG};
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
    background: {INPUT_BG};
}}
QScrollBar::handle:vertical {{
    background: {SCROLL_HANDLE};
    border-radius: 4px;
}}
QStatusBar {{
    background: {INPUT_BG};
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
    background: {INPUT_BG};
}}
QCheckBox::indicator:checked {{
    background: {NEON_GREEN};
    border: 1px solid {NEON_GREEN};
}}
QMenu {{
    background: {INPUT_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
}}
QMenu::item:selected {{
    background: {MENU_SELECTED};
}}
"""


DEFAULT_THEME = "Standard"
PINK_PUPA_THEME = "Pink Pupa (Girlfirend Version)"
MIDNIGHT_BLUE_THEME = "Midnight Blue"
MONO_MINIMAL_THEME = "Mono Minimal"

THEMES = {
    DEFAULT_THEME: _build_theme(
        accent="#39FF14",
        bg_base="#0A0D0B",
        bg_darker="#050605",
        surface="#0F1412",
        panel="#101815",
        border="#1C2A22",
        text="#E6FFE0",
        text_muted="#8FB39A",
        bg_gradient="#0F1512",
        topbar_start="#0B0F0D",
        topbar_end="#111815",
        input_bg="#0B0F0E",
        bubble_bg="#0E1411",
        bubble_border="#1B2B22",
        bubble_self_bg="#0E1A12",
        bubble_self_border="#2C5C38",
        primary_text="#041007",
        accent_hover="#6BFF47",
        selection_bg="#1E3D2A",
        file_border="#1E3326",
        scroll_handle="#1D4021",
        menu_selected="#143018",
    ),
    PINK_PUPA_THEME: _build_theme(
        accent="#FF6FB8",
        bg_base="#0E0A0F",
        bg_darker="#060507",
        surface="#141015",
        panel="#18111B",
        border="#2A2130",
        text="#FFE8F4",
        text_muted="#C2A9BC",
        bg_gradient="#141019",
        topbar_start="#140F16",
        topbar_end="#1A141C",
        input_bg="#130E16",
        bubble_bg="#16101B",
        bubble_border="#2A2332",
        bubble_self_bg="#1C1224",
        bubble_self_border="#5C2E64",
        primary_text="#12070F",
        accent_hover="#FF9AD9",
        selection_bg="#3A2640",
        file_border="#352238",
        scroll_handle="#3A2A42",
        menu_selected="#2A1B2F",
    ),
    MIDNIGHT_BLUE_THEME: _build_theme(
        accent="#49C8FF",
        bg_base="#0A0C12",
        bg_darker="#05070B",
        surface="#111622",
        panel="#141A28",
        border="#233045",
        text="#E7F3FF",
        text_muted="#9BB0C7",
        bg_gradient="#121826",
        topbar_start="#0D121C",
        topbar_end="#151C2A",
        input_bg="#0F141F",
        bubble_bg="#101722",
        bubble_border="#1F2A3D",
        bubble_self_bg="#132032",
        bubble_self_border="#3B6EA5",
        primary_text="#06111E",
        accent_hover="#7AD8FF",
        selection_bg="#1F3552",
        file_border="#243248",
        scroll_handle="#284A6E",
        menu_selected="#1B2A3F",
    ),
    MONO_MINIMAL_THEME: _build_theme(
        accent="#CFCFCF",
        bg_base="#0C0C0C",
        bg_darker="#070707",
        surface="#111111",
        panel="#151515",
        border="#262626",
        text="#F2F2F2",
        text_muted="#A0A0A0",
        bg_gradient="#121212",
        topbar_start="#0E0E0E",
        topbar_end="#141414",
        input_bg="#101010",
        bubble_bg="#121212",
        bubble_border="#2A2A2A",
        bubble_self_bg="#161616",
        bubble_self_border="#3A3A3A",
        primary_text="#0B0B0B",
        accent_hover="#FFFFFF",
        selection_bg="#2B2B2B",
        file_border="#2C2C2C",
        scroll_handle="#3A3A3A",
        menu_selected="#1E1E1E",
    ),
}
THEMES.setdefault("Pink Pupa", THEMES[PINK_PUPA_THEME])

THEME_CHOICES = [
    DEFAULT_THEME,
    PINK_PUPA_THEME,
    MIDNIGHT_BLUE_THEME,
    MONO_MINIMAL_THEME,
]


def apply_theme(app: QApplication, theme_name: str | None = None) -> None:
    key = theme_name or DEFAULT_THEME
    app.setStyleSheet(THEMES.get(key, THEMES[DEFAULT_THEME]))
