from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs

from net import protocol


class ApiService:
    def __init__(
        self,
        token: str,
        enabled: bool,
        send_text: Callable[[dict[str, Any]], None],
        send_files: Callable[[list[str]], None],
        send_edit: Callable[[str, str], None],
        send_undo: Callable[[str], None],
        send_pin: Callable[[str, str], None],
        send_unpin: Callable[[str], None],
        get_peers: Callable[[], list[dict[str, Any]]],
        get_history: Callable[[], list[dict[str, Any]]],
        get_pinned: Callable[[], dict[str, Any] | None],
        get_queue_size: Callable[[], int],
        get_self_info: Callable[[], dict[str, Any]],
    ) -> None:
        self._token = token
        self._enabled = enabled
        self._send_text = send_text
        self._send_files = send_files
        self._send_edit = send_edit
        self._send_undo = send_undo
        self._send_pin = send_pin
        self._send_unpin = send_unpin
        self._get_peers = get_peers
        self._get_history = get_history
        self._get_pinned = get_pinned
        self._get_queue_size = get_queue_size
        self._get_self_info = get_self_info

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_token(self, token: str) -> None:
        self._token = token

    def handle(
        self,
        method: str,
        path: str,
        query: str,
        body: bytes,
        headers: dict[str, str],
        server_port: int,
    ) -> tuple[int, bytes, str]:
        clean_path = path.rstrip("/") or "/"
        if method == "GET" and clean_path in {"/api/v1", "/api/v1/"}:
            payload = self.describe(server_port)
            return self._json_response(200, payload)
        if method == "GET" and clean_path == "/api/v1/help":
            return 200, self._help_text(server_port).encode("utf-8"), "text/plain; charset=utf-8"

        if not self._enabled:
            return self._json_response(404, {"ok": False, "error": "API disabled"})

        if not self._authorized(headers, query):
            return self._json_response(401, {"ok": False, "error": "Unauthorized"})

        if clean_path == "/api/v1/status" and method == "GET":
            return self._json_response(200, self._status_payload(server_port))
        if clean_path == "/api/v1/peers" and method == "GET":
            return self._json_response(200, {"ok": True, "peers": self._get_peers()})
        if clean_path == "/api/v1/messages" and method == "GET":
            limit = self._parse_limit(query)
            history = self._get_history()
            return self._json_response(
                200,
                {"ok": True, "messages": history[-limit:] if limit else history},
            )
        if clean_path == "/api/v1/pin" and method == "GET":
            pinned = self._get_pinned()
            if not pinned:
                return self._json_response(200, {"ok": True, "pinned": None})
            return self._json_response(200, {"ok": True, "pinned": pinned})

        if method != "POST":
            return self._json_response(405, {"ok": False, "error": "Method not allowed"})

        payload, error = self._parse_json(body)
        if error:
            return self._json_response(400, {"ok": False, "error": error})

        if clean_path == "/api/v1/send":
            return self._handle_send(payload)
        if clean_path == "/api/v1/send/file":
            return self._handle_send_file(payload)
        if clean_path == "/api/v1/edit":
            return self._handle_edit(payload)
        if clean_path == "/api/v1/undo":
            return self._handle_undo(payload)
        if clean_path == "/api/v1/pin":
            return self._handle_pin(payload)
        if clean_path == "/api/v1/unpin":
            return self._handle_unpin(payload)

        return self._json_response(404, {"ok": False, "error": "Not found"})

    def describe(self, server_port: int) -> dict[str, Any]:
        base_url = f"http://127.0.0.1:{server_port}/api/v1"
        return {
            "name": "Walkuer LAN Chat API",
            "version": "v1",
            "base_url": base_url,
            "auth": {
                "required": True,
                "header": "X-API-Token",
                "query": "token",
            },
            "notes": [
                "Localhost only (127.0.0.1).",
                "All POST endpoints require a valid API token.",
                "Text size limit: 8 KB UTF-8.",
                "File send expects a local file path on this machine.",
            ],
            "endpoints": [
                {
                    "method": "GET",
                    "path": "/api/v1/",
                    "description": "Self description for AI clients.",
                },
                {"method": "GET", "path": "/api/v1/help", "description": "Plain text help."},
                {"method": "GET", "path": "/api/v1/status", "description": "API and network status."},
                {"method": "GET", "path": "/api/v1/peers", "description": "List online peers."},
                {"method": "GET", "path": "/api/v1/messages?limit=50", "description": "Recent messages."},
                {"method": "GET", "path": "/api/v1/pin", "description": "Get pinned message."},
                {
                    "method": "POST",
                    "path": "/api/v1/send",
                    "description": "Send chat message.",
                    "request": {"text": "hello", "reply_to": "optional"},
                },
                {
                    "method": "POST",
                    "path": "/api/v1/send/file",
                    "description": "Send local file by path.",
                    "request": {"path": "C:\\\\path\\\\file.txt"},
                },
                {"method": "POST", "path": "/api/v1/edit", "request": {"message_id": "...", "text": "new"}},
                {"method": "POST", "path": "/api/v1/undo", "request": {"message_id": "..."}},
                {"method": "POST", "path": "/api/v1/pin", "request": {"message_id": "..."}},
                {"method": "POST", "path": "/api/v1/unpin", "request": {"message_id": "..."}},
            ],
        }

    def _help_text(self, server_port: int) -> str:
        base_url = f"http://127.0.0.1:{server_port}/api/v1"
        return (
            "Walkuer LAN Chat API\\n"
            f"Base: {base_url}\\n"
            "Auth: X-API-Token header or ?token=...\\n"
            "GET  /api/v1/          self description\\n"
            "GET  /api/v1/status    status + queue\\n"
            "GET  /api/v1/peers     online peers\\n"
            "GET  /api/v1/messages  recent messages\\n"
            "POST /api/v1/send      send chat\\n"
            "POST /api/v1/send/file send file by path\\n"
            "POST /api/v1/edit      edit message\\n"
            "POST /api/v1/undo      undo message\\n"
            "POST /api/v1/pin       pin message\\n"
            "POST /api/v1/unpin     unpin message\\n"
        )

    def _status_payload(self, server_port: int) -> dict[str, Any]:
        info = self._get_self_info()
        return {
            "ok": True,
            "api_enabled": self._enabled,
            "api_base_url": f"http://127.0.0.1:{server_port}/api/v1",
            "queue_size": self._get_queue_size(),
            "self": info,
        }

    def _handle_send(self, payload: dict[str, Any]) -> tuple[int, bytes, str]:
        text = (payload.get("text") or "").strip()
        if not text:
            return self._json_response(400, {"ok": False, "error": "Missing text"})
        if len(text.encode("utf-8")) > protocol.MAX_TEXT_BYTES:
            return self._json_response(400, {"ok": False, "error": "Text too long (max 8 KB)"})
        message_id = payload.get("message_id") or str(uuid.uuid4())
        send_payload = dict(payload)
        send_payload["text"] = text
        send_payload["message_id"] = message_id
        send_payload["_via_api"] = True
        self._send_text(send_payload)
        return self._json_response(200, {"ok": True, "message_id": message_id})

    def _handle_send_file(self, payload: dict[str, Any]) -> tuple[int, bytes, str]:
        path = (payload.get("path") or "").strip()
        if not path:
            return self._json_response(400, {"ok": False, "error": "Missing path"})
        if not Path(path).exists():
            return self._json_response(404, {"ok": False, "error": "File not found"})
        self._send_files([path])
        return self._json_response(200, {"ok": True, "queued": True})

    def _handle_edit(self, payload: dict[str, Any]) -> tuple[int, bytes, str]:
        message_id = (payload.get("message_id") or "").strip()
        text = (payload.get("text") or "").strip()
        if not message_id or not text:
            return self._json_response(400, {"ok": False, "error": "Missing message_id or text"})
        if len(text.encode("utf-8")) > protocol.MAX_TEXT_BYTES:
            return self._json_response(400, {"ok": False, "error": "Text too long (max 8 KB)"})
        self._send_edit(message_id, text)
        return self._json_response(200, {"ok": True})

    def _handle_undo(self, payload: dict[str, Any]) -> tuple[int, bytes, str]:
        message_id = (payload.get("message_id") or "").strip()
        if not message_id:
            return self._json_response(400, {"ok": False, "error": "Missing message_id"})
        self._send_undo(message_id)
        return self._json_response(200, {"ok": True})

    def _handle_pin(self, payload: dict[str, Any]) -> tuple[int, bytes, str]:
        message_id = (payload.get("message_id") or "").strip()
        if not message_id:
            return self._json_response(400, {"ok": False, "error": "Missing message_id"})
        preview = (payload.get("preview") or "").strip()
        if not preview:
            preview = self._preview_from_history(message_id)
        self._send_pin(message_id, preview)
        return self._json_response(200, {"ok": True})

    def _handle_unpin(self, payload: dict[str, Any]) -> tuple[int, bytes, str]:
        message_id = (payload.get("message_id") or "").strip()
        if not message_id:
            return self._json_response(400, {"ok": False, "error": "Missing message_id"})
        self._send_unpin(message_id)
        return self._json_response(200, {"ok": True})

    def _authorized(self, headers: dict[str, str], query: str) -> bool:
        token = headers.get("X-API-Token") or ""
        if not token:
            params = parse_qs(query or "")
            token = (params.get("token") or [""])[0]
        return bool(token) and token == self._token

    def _parse_json(self, body: bytes) -> tuple[dict[str, Any], str | None]:
        if not body:
            return {}, None
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                return {}, "Invalid JSON payload"
            return payload, None
        except Exception:
            return {}, "Invalid JSON payload"

    def _parse_limit(self, query: str) -> int:
        params = parse_qs(query or "")
        raw = (params.get("limit") or [""])[0]
        try:
            value = int(raw)
        except Exception:
            value = 50
        return max(1, min(200, value))

    def _json_response(self, status: int, payload: dict[str, Any]) -> tuple[int, bytes, str]:
        return status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"

    def _preview_from_history(self, message_id: str) -> str:
        history = self._get_history()
        for msg in reversed(history):
            if msg.get("message_id") == message_id:
                text = msg.get("text") or msg.get("filename") or ""
                return self._trim_text(text)
        return ""

    @staticmethod
    def _trim_text(text: str, max_len: int = 120) -> str:
        cleaned = " ".join((text or "").split())
        if len(cleaned) <= max_len:
            return cleaned
        return cleaned[: max_len - 1] + "."
