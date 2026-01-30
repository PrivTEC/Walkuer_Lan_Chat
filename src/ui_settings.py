from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QColorDialog,
)

from config_store import ConfigStore
from theme import DEFAULT_THEME, THEME_CHOICES
from util.images import load_avatar_pixmap
from util.i18n import available_languages, set_language, t


class SettingsDialog(QDialog):
    saved = Signal()

    def __init__(self, store: ConfigStore, api_url: str = "", force: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self._pending_avatar: str | None = None
        self._force = force
        self._api_url = api_url

        self.setWindowTitle(t("settings.title"))
        self.setModal(True)
        self.setMinimumWidth(420)
        if force:
            self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 12, 14, 12)

        name_label = QLabel(t("settings.username"))
        self.name_input = QLineEdit(store.config.user_name)

        avatar_label = QLabel(t("settings.avatar"))
        self.avatar_preview = QLabel()
        self.avatar_preview.setObjectName("avatarPreview")
        self.avatar_preview.setFixedSize(72, 72)
        self.avatar_preview.setAlignment(Qt.AlignCenter)

        self._refresh_preview()

        avatar_buttons = QHBoxLayout()
        choose_btn = QPushButton(t("settings.avatar_choose"))
        remove_btn = QPushButton(t("settings.avatar_remove"))
        choose_btn.clicked.connect(self._choose_avatar)
        remove_btn.clicked.connect(self._remove_avatar)
        avatar_buttons.addWidget(choose_btn)
        avatar_buttons.addWidget(remove_btn)

        theme_label = QLabel(t("settings.theme"))
        self.theme_select = QComboBox()
        self.theme_select.addItems(THEME_CHOICES)
        current_theme = store.config.theme or DEFAULT_THEME
        index = self.theme_select.findText(current_theme)
        if index < 0:
            index = 0
        self.theme_select.setCurrentIndex(index)

        language_label = QLabel(t("settings.language"))
        self.language_select = QComboBox()
        self._language_codes: list[str] = []
        for code, name in available_languages():
            self._language_codes.append(code)
            self.language_select.addItem(name)
        current_lang = store.config.language or "de-DE"
        if current_lang in self._language_codes:
            self.language_select.setCurrentIndex(self._language_codes.index(current_lang))

        chat_bg_label = QLabel(t("settings.chat_bg"))
        self.chat_bg_mode = QComboBox()
        self._bg_mode_values = ["off", "color", "image"]
        self.chat_bg_mode.addItems(
            [t("settings.chat_bg_off"), t("settings.chat_bg_color"), t("settings.chat_bg_image")]
        )
        current_mode = store.config.chat_bg_mode or "off"
        if current_mode in self._bg_mode_values:
            self.chat_bg_mode.setCurrentIndex(self._bg_mode_values.index(current_mode))
        else:
            self.chat_bg_mode.setCurrentIndex(0)

        self.chat_bg_color = store.config.chat_bg_color or "#000000"
        self.chat_bg_color_btn = QPushButton()
        self.chat_bg_color_btn.clicked.connect(self._choose_chat_bg_color)
        self._update_chat_bg_color_button()

        self.chat_bg_image_path = QLineEdit(store.config.chat_bg_image_path or "")
        self.chat_bg_image_path.setReadOnly(True)
        self.chat_bg_image_btn = QPushButton(t("settings.chat_bg_choose"))
        self.chat_bg_image_btn.clicked.connect(self._choose_chat_bg_image)

        self.chat_bg_opacity = QSlider(Qt.Horizontal)
        self.chat_bg_opacity.setRange(0, 100)
        self.chat_bg_opacity.setValue(int(store.config.chat_bg_opacity or 12))
        self.chat_bg_opacity_label = QLabel(
            t("settings.opacity_label", value=self.chat_bg_opacity.value())
        )
        self.chat_bg_opacity.valueChanged.connect(
            lambda v: self.chat_bg_opacity_label.setText(t("settings.opacity_label", value=v))
        )

        self.sound_toggle = QCheckBox(t("settings.sound_toggle"))
        self.sound_toggle.setChecked(store.config.sound_enabled)

        self.tray_toggle = QCheckBox(t("settings.tray_toggle"))
        self.tray_toggle.setChecked(store.config.tray_notifications)

        self.expert_toggle = QCheckBox(t("settings.expert_toggle"))
        self.expert_toggle.setChecked(store.config.expert_mode)

        api_label = QLabel(t("settings.api_section"))
        self.api_toggle = QCheckBox(t("settings.api_toggle"))
        self.api_toggle.setChecked(store.config.api_enabled)

        api_url_label = QLabel(t("settings.api_url"))
        self.api_url_value = QLineEdit(api_url or "http://127.0.0.1:<port>/api/v1/")
        self.api_url_value.setReadOnly(True)

        api_token_label = QLabel(t("settings.api_token"))
        self.api_token_value = QLineEdit(store.config.api_token)
        self.api_token_value.setReadOnly(True)
        token_row = QHBoxLayout()
        token_row.addWidget(self.api_token_value, 1)
        token_regen = QPushButton(t("settings.api_token_regen"))
        token_regen.clicked.connect(self._regen_api_token)
        token_row.addWidget(token_regen)

        self.api_section = QFrame()
        api_layout = QVBoxLayout(self.api_section)
        api_layout.setContentsMargins(0, 0, 0, 0)
        api_layout.setSpacing(6)
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_toggle)
        api_layout.addWidget(api_url_label)
        api_layout.addWidget(self.api_url_value)
        api_layout.addWidget(api_token_label)
        api_layout.addLayout(token_row)

        save_btn = QPushButton(t("common.save"))
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)

        layout.addWidget(name_label)
        layout.addWidget(self.name_input)
        layout.addWidget(avatar_label)
        layout.addWidget(self.avatar_preview, alignment=Qt.AlignLeft)
        layout.addLayout(avatar_buttons)
        layout.addWidget(theme_label)
        layout.addWidget(self.theme_select)
        layout.addWidget(language_label)
        layout.addWidget(self.language_select)
        layout.addWidget(chat_bg_label)
        layout.addWidget(self.chat_bg_mode)

        self.chat_bg_color_label = QLabel(t("settings.chat_bg_color_label"))
        layout.addWidget(self.chat_bg_color_label)
        layout.addWidget(self.chat_bg_color_btn)

        self.chat_bg_image_label = QLabel(t("settings.chat_bg_image_label"))
        layout.addWidget(self.chat_bg_image_label)
        layout.addWidget(self.chat_bg_image_path)
        layout.addWidget(self.chat_bg_image_btn)

        layout.addWidget(self.chat_bg_opacity_label)
        layout.addWidget(self.chat_bg_opacity)
        layout.addWidget(self.sound_toggle)
        layout.addWidget(self.tray_toggle)
        layout.addWidget(self.expert_toggle)
        layout.addWidget(self.api_section)
        layout.addStretch(1)
        layout.addWidget(save_btn, alignment=Qt.AlignRight)

        if not force:
            cancel_btn = QPushButton(t("common.cancel"))
            cancel_btn.clicked.connect(self.reject)
            layout.addWidget(cancel_btn, alignment=Qt.AlignRight)

        self.expert_toggle.toggled.connect(self._update_expert_visibility)
        self.chat_bg_mode.currentIndexChanged.connect(self._update_chat_bg_controls)
        self._update_chat_bg_controls()
        self._update_expert_visibility()

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
            t("settings.avatar_choose_title"),
            "",
            t("settings.images_filter")
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

    def _update_chat_bg_color_button(self) -> None:
        self.chat_bg_color_btn.setText(self.chat_bg_color)
        self.chat_bg_color_btn.setStyleSheet(f"background: {self.chat_bg_color};")

    def _choose_chat_bg_color(self) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            self.chat_bg_color = color.name()
            self._update_chat_bg_color_button()

    def _choose_chat_bg_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("settings.chat_bg_choose_title"),
            "",
            t("settings.images_filter")
        )
        if file_path:
            self.chat_bg_image_path.setText(file_path)

    def _update_chat_bg_controls(self) -> None:
        mode = self._bg_mode_values[self.chat_bg_mode.currentIndex()]
        is_color = mode == "color"
        is_image = mode == "image"
        self.chat_bg_color_btn.setEnabled(is_color)
        self.chat_bg_image_btn.setEnabled(is_image)
        self.chat_bg_image_path.setEnabled(is_image)
        self.chat_bg_color_label.setVisible(is_color)
        self.chat_bg_color_btn.setVisible(is_color)
        self.chat_bg_image_label.setVisible(is_image)
        self.chat_bg_image_path.setVisible(is_image)
        self.chat_bg_image_btn.setVisible(is_image)
        self.chat_bg_opacity.setEnabled(is_color or is_image)
        self.chat_bg_opacity_label.setEnabled(is_color or is_image)

    def _save(self) -> None:
        name = self.name_input.text().strip() or t("user.default_name")
        self._store.config.user_name = name
        self._store.config.theme = self.theme_select.currentText()
        if self._language_codes:
            self._store.config.language = self._language_codes[self.language_select.currentIndex()]
        self._store.config.sound_enabled = self.sound_toggle.isChecked()
        self._store.config.tray_notifications = self.tray_toggle.isChecked()
        self._store.config.api_enabled = self.api_toggle.isChecked()
        self._store.config.expert_mode = self.expert_toggle.isChecked()
        self._store.config.first_run_complete = True
        self._store.config.chat_bg_mode = self._bg_mode_values[self.chat_bg_mode.currentIndex()]
        self._store.config.chat_bg_color = self.chat_bg_color
        self._store.config.chat_bg_opacity = int(self.chat_bg_opacity.value())
        self._store.config.chat_bg_image_path = self.chat_bg_image_path.text().strip()

        if self._pending_avatar is not None:
            if self._pending_avatar == "":
                self._store.remove_avatar()
            else:
                self._store.set_avatar_from_path(self._pending_avatar)

        self._store.save()
        set_language(self._store.config.language)
        parent = self.parent()
        if parent is not None and hasattr(parent, "_apply_chat_background_from_config"):
            parent._apply_chat_background_from_config()
        if parent is not None and hasattr(parent, "apply_translations"):
            parent.apply_translations()
        self.saved.emit()
        self.accept()

    def closeEvent(self, event):  # noqa: N802 - Qt naming
        if self._force:
            event.ignore()
        else:
            event.accept()

    def _update_expert_visibility(self) -> None:
        if hasattr(self, "api_section"):
            self.api_section.setVisible(self.expert_toggle.isChecked())
