from __future__ import annotations

import json
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any


class DedupCache:
    def __init__(self, max_items: int = 2000, ttl_seconds: int = 900) -> None:
        self._max = max_items
        self._ttl = ttl_seconds
        self._items: OrderedDict[str, float] = OrderedDict()

    def seen(self, message_id: str) -> bool:
        now = time.time()
        self._prune(now)
        if message_id in self._items:
            return True
        self._items[message_id] = now
        if len(self._items) > self._max:
            self._items.popitem(last=False)
        return False

    def _prune(self, now: float) -> None:
        expired = [k for k, v in self._items.items() if now - v > self._ttl]
        for key in expired:
            self._items.pop(key, None)


class HistoryStore:
    def __init__(self, path: Path, max_items: int = 500) -> None:
        self.path = path
        self.max_items = max_items
        self.items: list[dict[str, Any]] = []

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            self.items = []
            return self.items
        items: list[dict[str, Any]] = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if isinstance(msg, dict):
                            items.append(msg)
                    except Exception:
                        continue
        except Exception:
            items = []
        self.items = items[-self.max_items :]
        return self.items

    def append(self, msg: dict[str, Any]) -> None:
        self.items.append(msg)
        if len(self.items) > self.max_items:
            self.items = self.items[-self.max_items :]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                for item in self.items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
        except Exception:
            pass
