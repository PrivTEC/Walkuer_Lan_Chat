from __future__ import annotations

import json
import time
from typing import Any

MULTICAST_GROUP = "239.255.77.77"
UDP_PORT = 51337
TTL = 1
VERSION = 1

MAX_TEXT_BYTES = 8 * 1024
MAX_UDP_BYTES = 50 * 1024


def now_ms() -> int:
    return int(time.time() * 1000)


def encode_message(payload: dict[str, Any]) -> bytes | None:
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(data) > MAX_UDP_BYTES:
            return None
        return data
    except Exception:
        return None


def parse_message(data: bytes) -> dict[str, Any] | None:
    try:
        payload = json.loads(data.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        if payload.get("v") != VERSION:
            return None
        if payload.get("t") not in {"HELLO", "CHAT", "FILE"}:
            return None
        return payload
    except Exception:
        return None


def build_hello(
    sender_id: str,
    name: str,
    avatar_sha256: str,
    http_port: int,
    typing: bool = False,
) -> dict[str, Any]:
    return {
        "t": "HELLO",
        "v": VERSION,
        "sender_id": sender_id,
        "name": name,
        "avatar_sha256": avatar_sha256 or "",
        "http_port": int(http_port or 0),
        "typing": bool(typing),
        "ts": now_ms(),
    }


def build_chat(sender_id: str, name: str, avatar_sha256: str, text: str) -> dict[str, Any]:
    return {
        "t": "CHAT",
        "v": VERSION,
        "message_id": _uuid(),
        "sender_id": sender_id,
        "name": name,
        "avatar_sha256": avatar_sha256 or "",
        "text": text,
        "ts": now_ms(),
    }


def build_reaction(sender_id: str, name: str, avatar_sha256: str, target_id: str, emoji: str) -> dict[str, Any]:
    return {
        "t": "CHAT",
        "v": VERSION,
        "message_id": _uuid(),
        "sender_id": sender_id,
        "name": name,
        "avatar_sha256": avatar_sha256 or "",
        "subtype": "REACT",
        "target_id": target_id,
        "emoji": emoji,
        "ts": now_ms(),
    }


def build_edit(
    sender_id: str,
    name: str,
    avatar_sha256: str,
    target_id: str,
    text: str,
) -> dict[str, Any]:
    return {
        "t": "CHAT",
        "v": VERSION,
        "message_id": _uuid(),
        "sender_id": sender_id,
        "name": name,
        "avatar_sha256": avatar_sha256 or "",
        "subtype": "EDIT",
        "target_id": target_id,
        "text": text,
        "ts": now_ms(),
    }


def build_undo(sender_id: str, name: str, avatar_sha256: str, target_id: str) -> dict[str, Any]:
    return {
        "t": "CHAT",
        "v": VERSION,
        "message_id": _uuid(),
        "sender_id": sender_id,
        "name": name,
        "avatar_sha256": avatar_sha256 or "",
        "subtype": "UNDO",
        "target_id": target_id,
        "ts": now_ms(),
    }


def build_pin(sender_id: str, name: str, avatar_sha256: str, target_id: str, preview: str) -> dict[str, Any]:
    return {
        "t": "CHAT",
        "v": VERSION,
        "message_id": _uuid(),
        "sender_id": sender_id,
        "name": name,
        "avatar_sha256": avatar_sha256 or "",
        "subtype": "PIN",
        "target_id": target_id,
        "preview": preview,
        "ts": now_ms(),
    }


def build_unpin(sender_id: str, name: str, avatar_sha256: str, target_id: str) -> dict[str, Any]:
    return {
        "t": "CHAT",
        "v": VERSION,
        "message_id": _uuid(),
        "sender_id": sender_id,
        "name": name,
        "avatar_sha256": avatar_sha256 or "",
        "subtype": "UNPIN",
        "target_id": target_id,
        "ts": now_ms(),
    }


def build_file(
    sender_id: str,
    name: str,
    avatar_sha256: str,
    file_id: str,
    filename: str,
    size: int,
    sha256: str,
    url: str,
) -> dict[str, Any]:
    return {
        "t": "FILE",
        "v": VERSION,
        "message_id": _uuid(),
        "sender_id": sender_id,
        "name": name,
        "avatar_sha256": avatar_sha256 or "",
        "file_id": file_id,
        "filename": filename,
        "size": int(size),
        "sha256": sha256,
        "url": url,
        "ts": now_ms(),
    }


def _uuid() -> str:
    import uuid

    return str(uuid.uuid4())
