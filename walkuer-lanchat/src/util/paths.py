from __future__ import annotations

import os
from pathlib import Path

ORG_DIRNAME = "WalkuerTechnology"
APP_DIRNAME = "LanChat"


def _appdata_root() -> Path:
    root = os.getenv("APPDATA")
    if root:
        return Path(root)
    return Path.home() / "AppData" / "Roaming"


def app_data_dir() -> Path:
    return _appdata_root() / ORG_DIRNAME / APP_DIRNAME


def config_path() -> Path:
    return app_data_dir() / "config.json"


def history_path() -> Path:
    return app_data_dir() / "history.jsonl"


def logs_dir() -> Path:
    return app_data_dir() / "logs"


def downloads_dir() -> Path:
    user = os.getenv("USERPROFILE")
    if user:
        base = Path(user)
    else:
        base = Path.home()
    return base / "Downloads" / "WalkuerLanChat"


def ensure_dirs() -> None:
    app_data_dir().mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
    downloads_dir().mkdir(parents=True, exist_ok=True)
