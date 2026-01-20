from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QObject, Signal


class DiscoveryTracker(QObject):
    updated = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._peers: dict[str, dict[str, Any]] = {}

    def update_hello(self, msg: dict[str, Any], sender_ip: str) -> None:
        sender_id = msg.get("sender_id")
        if not sender_id:
            return
        now = time.time()
        was_count = len(self._peers)
        self._peers[sender_id] = {
            "name": msg.get("name") or "",
            "avatar_sha256": msg.get("avatar_sha256") or "",
            "http_port": int(msg.get("http_port") or 0),
            "sender_ip": sender_ip,
            "last_seen": now,
        }
        if len(self._peers) != was_count:
            self.updated.emit(len(self._peers))

    def prune(self, ttl_seconds: int = 8) -> None:
        now = time.time()
        before = len(self._peers)
        self._peers = {
            k: v for k, v in self._peers.items() if now - v.get("last_seen", 0) <= ttl_seconds
        }
        if len(self._peers) != before:
            self.updated.emit(len(self._peers))

    def online_count(self) -> int:
        return len(self._peers)

    def peer_info(self, sender_id: str) -> dict[str, Any] | None:
        return self._peers.get(sender_id)
