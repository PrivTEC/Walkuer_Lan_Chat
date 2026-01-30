from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_LANG_CODE = "de-DE"
_TRANSLATIONS: dict[str, str] = {}
_META: dict[str, Any] = {}

_LEGACY_LANGUAGE_CODES = {
    "de_DE": "de-DE",
    "en_EN": "en-EN",
}


def _normalize_language_code(code: str | None) -> str:
    if not code:
        return "de-DE"
    return _LEGACY_LANGUAGE_CODES.get(code, code)


def _lang_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / "lang"


def available_languages() -> list[tuple[str, str]]:
    langs: list[tuple[str, str]] = []
    lang_dir = _lang_dir()
    if not lang_dir.exists():
        return [("de-DE", "Deutsch")]
    for path in sorted(lang_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = raw.get("_meta", {}) if isinstance(raw, dict) else {}
        code = meta.get("code") or path.stem
        name = meta.get("name") or code
        langs.append((code, name))
    return langs


def language_code() -> str:
    return _LANG_CODE


def load_language(code: str) -> None:
    global _LANG_CODE, _TRANSLATIONS, _META
    code = _normalize_language_code(code)
    lang_dir = _lang_dir()
    target = lang_dir / f"{code}.json"
    if not target.exists():
        target = lang_dir / "de-DE.json"
    data: dict[str, Any] = {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    meta = data.get("_meta", {}) if isinstance(data, dict) else {}
    _TRANSLATIONS = {k: v for k, v in data.items() if isinstance(k, str) and not k.startswith("_")}
    _META = meta
    _LANG_CODE = meta.get("code") or target.stem


def set_language(code: str) -> None:
    load_language(code)


def t(key: str, **kwargs: Any) -> str:
    text = _TRANSLATIONS.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
