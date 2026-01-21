from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from util.filehash import sha256_file
from util.paths import app_data_dir, config_path, ensure_dirs


@dataclass
class AppConfig:
    sender_id: str
    user_name: str
    avatar_path: str
    avatar_sha256: str
    sound_enabled: bool
    tray_notifications: bool
    first_run_complete: bool


class ConfigStore:
    def __init__(self) -> None:
        self.path = config_path()
        self.config = self._default_config()

    def _default_config(self) -> AppConfig:
        default_name = os.getenv("USERNAME") or "User"
        return AppConfig(
            sender_id=str(uuid.uuid4()),
            user_name=default_name,
            avatar_path="",
            avatar_sha256="",
            sound_enabled=True,
            tray_notifications=True,
            first_run_complete=False,
        )

    def load(self) -> AppConfig:
        ensure_dirs()
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self.config = AppConfig(
                    sender_id=raw.get("sender_id") or str(uuid.uuid4()),
                    user_name=raw.get("user_name") or self.config.user_name,
                    avatar_path=raw.get("avatar_path") or "",
                    avatar_sha256=raw.get("avatar_sha256") or "",
                    sound_enabled=bool(raw.get("sound_enabled", True)),
                    tray_notifications=bool(raw.get("tray_notifications", True)),
                    first_run_complete=bool(raw.get("first_run_complete", False)),
                )
            except Exception:
                self.config = self._default_config()
        else:
            self.config = self._default_config()

        if self.config.avatar_path:
            path = Path(self.config.avatar_path)
            if not path.exists():
                self.config.avatar_path = ""
                self.config.avatar_sha256 = ""
            elif not self.config.avatar_sha256:
                try:
                    self.config.avatar_sha256 = sha256_file(path)
                except Exception:
                    self.config.avatar_sha256 = ""

        if not self.config.sender_id:
            self.config.sender_id = str(uuid.uuid4())
        return self.config

    def save(self) -> None:
        ensure_dirs()
        self.path.write_text(json.dumps(asdict(self.config), indent=2, ensure_ascii=False), encoding="utf-8")

    def set_avatar_from_path(self, src_path: str) -> None:
        src = Path(src_path)
        if not src.exists():
            return
        ensure_dirs()
        dest_dir = app_data_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"avatar{src.suffix.lower()}"
        try:
            shutil.copyfile(src, dest)
            self.config.avatar_path = str(dest)
            self.config.avatar_sha256 = sha256_file(dest)
        except Exception:
            self.config.avatar_path = ""
            self.config.avatar_sha256 = ""

    def remove_avatar(self) -> None:
        if self.config.avatar_path:
            try:
                Path(self.config.avatar_path).unlink(missing_ok=True)
            except Exception:
                pass
        self.config.avatar_path = ""
        self.config.avatar_sha256 = ""
