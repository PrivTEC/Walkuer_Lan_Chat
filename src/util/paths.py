from __future__ import annotations

import os
import shutil
from pathlib import Path

DOT_DIRNAME = ".walkuer-lanchat"
LEGACY_ORG_DIRNAME = "WalkuerTechnology"
LEGACY_APP_DIRNAME = "LanChat"


def _legacy_appdata_root() -> Path:
    root = os.getenv("APPDATA")
    if root:
        return Path(root)
    return Path.home() / "AppData" / "Roaming"


def legacy_app_data_dir() -> Path:
    return _legacy_appdata_root() / LEGACY_ORG_DIRNAME / LEGACY_APP_DIRNAME


def app_data_dir() -> Path:
    return Path.home() / DOT_DIRNAME


def config_path() -> Path:
    return app_data_dir() / "config.json"


def history_path() -> Path:
    return app_data_dir() / "history.jsonl"


def logs_dir() -> Path:
    return app_data_dir() / "logs"


def downloads_dir() -> Path:
    return attachments_dir()


def avatars_dir() -> Path:
    return app_data_dir() / "avatars"


def avatar_cache_path(sha256: str) -> Path:
    return avatars_dir() / f"{sha256}.png"


def attachments_dir() -> Path:
    return app_data_dir() / "attachments"


def attachment_cache_path(file_id: str, filename: str) -> Path:
    suffix = Path(filename).suffix
    return attachments_dir() / f"{file_id}{suffix}"


def migrate_legacy() -> None:
    legacy = legacy_app_data_dir()
    if not legacy.exists():
        return
    target = app_data_dir()
    target.mkdir(parents=True, exist_ok=True)

    for name in ("config.json", "history.jsonl"):
        src = legacy / name
        dst = target / name
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

    legacy_avatars = legacy / "avatars"
    target_avatars = avatars_dir()
    if legacy_avatars.exists() and not target_avatars.exists():
        try:
            shutil.copytree(legacy_avatars, target_avatars)
        except Exception:
            pass


def ensure_dirs() -> None:
    migrate_legacy()
    app_data_dir().mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
    downloads_dir().mkdir(parents=True, exist_ok=True)
    avatars_dir().mkdir(parents=True, exist_ok=True)
    attachments_dir().mkdir(parents=True, exist_ok=True)
