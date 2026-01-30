from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QPushButton, QVBoxLayout

from config_store import ConfigStore
from util.i18n import available_languages, set_language, t


class LanguageDialog(QDialog):
    saved = Signal()

    def __init__(self, store: ConfigStore, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self._language_codes: list[str] = []

        self.setWindowTitle(t("lang.title"))
        self.setModal(True)
        self.setMinimumWidth(360)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 12, 14, 12)

        label = QLabel(t("lang.prompt"))
        self.language_select = QComboBox()
        for code, name in available_languages():
            self._language_codes.append(code)
            self.language_select.addItem(name)
        current_lang = store.config.language or "de-DE"
        if current_lang in self._language_codes:
            self.language_select.setCurrentIndex(self._language_codes.index(current_lang))

        save_btn = QPushButton(t("common.save"))
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)

        layout.addWidget(label)
        layout.addWidget(self.language_select)
        layout.addWidget(save_btn, alignment=Qt.AlignRight)

    def _save(self) -> None:
        if self._language_codes:
            self._store.config.language = self._language_codes[self.language_select.currentIndex()]
        self._store.config.first_run_complete = True
        self._store.save()
        set_language(self._store.config.language)
        parent = self.parent()
        if parent is not None and hasattr(parent, "apply_translations"):
            parent.apply_translations()
        self.saved.emit()
        self.accept()
