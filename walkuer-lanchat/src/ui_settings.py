from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from config_store import ConfigStore
from theme import DEFAULT_THEME, THEME_CHOICES
from util.images import load_avatar_pixmap


class SettingsDialog(QDialog):
    saved = Signal()

    def __init__(self, store: ConfigStore, api_url: str = "", force: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self._pending_avatar: str | None = None
        self._force = force
        self._api_url = api_url

        self.setWindowTitle("Einstellungen")
        self.setModal(True)
        self.setMinimumWidth(420)
        if force:
            self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 12, 14, 12)

        name_label = QLabel("Username")
        self.name_input = QLineEdit(store.config.user_name)

        avatar_label = QLabel("Avatar")
        self.avatar_preview = QLabel()
        self.avatar_preview.setObjectName("avatarPreview")
        self.avatar_preview.setFixedSize(72, 72)
        self.avatar_preview.setAlignment(Qt.AlignCenter)

        self._refresh_preview()

        avatar_buttons = QHBoxLayout()
        choose_btn = QPushButton("Bild wählen...")
        remove_btn = QPushButton("Avatar entfernen")
        choose_btn.clicked.connect(self._choose_avatar)
        remove_btn.clicked.connect(self._remove_avatar)
        avatar_buttons.addWidget(choose_btn)
        avatar_buttons.addWidget(remove_btn)

        theme_label = QLabel("Theme")
        self.theme_select = QComboBox()
        self.theme_select.addItems(THEME_CHOICES)
        current_theme = store.config.theme or DEFAULT_THEME
        index = self.theme_select.findText(current_theme)
        if index < 0:
            index = 0
        self.theme_select.setCurrentIndex(index)

        self.sound_toggle = QCheckBox("Sound bei neuen Nachrichten")
        self.sound_toggle.setChecked(store.config.sound_enabled)

        self.tray_toggle = QCheckBox("Tray-Popups")
        self.tray_toggle.setChecked(store.config.tray_notifications)

        api_label = QLabel("Lokale API")
        self.api_toggle = QCheckBox("API aktivieren (localhost)")
        self.api_toggle.setChecked(store.config.api_enabled)

        api_url_label = QLabel("API URL")
        self.api_url_value = QLineEdit(api_url or "http://127.0.0.1:<port>/api/v1/")
        self.api_url_value.setReadOnly(True)

        api_token_label = QLabel("API Token")
        self.api_token_value = QLineEdit(store.config.api_token)
        self.api_token_value.setReadOnly(True)
        token_row = QHBoxLayout()
        token_row.addWidget(self.api_token_value, 1)
        token_regen = QPushButton("Token neu")
        token_regen.clicked.connect(self._regen_api_token)
        token_row.addWidget(token_regen)

        save_btn = QPushButton("Speichern")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)

        layout.addWidget(name_label)
        layout.addWidget(self.name_input)
        layout.addWidget(avatar_label)
        layout.addWidget(self.avatar_preview, alignment=Qt.AlignLeft)
        layout.addLayout(avatar_buttons)
        layout.addWidget(theme_label)
        layout.addWidget(self.theme_select)
        layout.addWidget(self.sound_toggle)
        layout.addWidget(self.tray_toggle)
        layout.addWidget(api_label)
        layout.addWidget(self.api_toggle)
        layout.addWidget(api_url_label)
        layout.addWidget(self.api_url_value)
        layout.addWidget(api_token_label)
        layout.addLayout(token_row)
        layout.addStretch(1)
        layout.addWidget(save_btn, alignment=Qt.AlignRight)

        if not force:
            cancel_btn = QPushButton("Abbrechen")
            cancel_btn.clicked.connect(self.reject)
            layout.addWidget(cancel_btn, alignment=Qt.AlignRight)

    def _refresh_preview(self) -> None:
        config = self._store.config
        if self._pending_avatar == "":
            avatar_path = ""
        elif self._pending_avatar:
            avatar_path = self._pending_avatar
        else:
            avatar_path = config.avatar_path
        pixmap = load_avatar_pixmap(avatar_path, config.user_name, config.avatar_sha256, 72)
        self.avatar_preview.setPixmap(pixmap)

    def _choose_avatar(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Avatar wählen",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self._pending_avatar = file_path
            self._refresh_preview()

    def _remove_avatar(self) -> None:
        self._pending_avatar = ""
        self._refresh_preview()

    def _regen_api_token(self) -> None:
        new_token = self._store.regenerate_api_token()
        self.api_token_value.setText(new_token)

    def _save(self) -> None:
        name = self.name_input.text().strip() or "User"
        self._store.config.user_name = name
        self._store.config.theme = self.theme_select.currentText()
        self._store.config.sound_enabled = self.sound_toggle.isChecked()
        self._store.config.tray_notifications = self.tray_toggle.isChecked()
        self._store.config.api_enabled = self.api_toggle.isChecked()
        self._store.config.first_run_complete = True

        if self._pending_avatar is not None:
            if self._pending_avatar == "":
                self._store.remove_avatar()
            else:
                self._store.set_avatar_from_path(self._pending_avatar)

        self._store.save()
        self.saved.emit()
        self.accept()

    def closeEvent(self, event):  # noqa: N802 - Qt naming
        if self._force:
            event.ignore()
        else:
            event.accept()
