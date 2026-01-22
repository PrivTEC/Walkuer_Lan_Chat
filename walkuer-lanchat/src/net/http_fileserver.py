from __future__ import annotations

import mimetypes
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from net.api_service import ApiService


class FileRegistry:
    def __init__(self) -> None:
        self._map: dict[str, Path] = {}
        self._avatars: dict[str, Path] = {}
        self._lock = threading.Lock()

    def register(self, file_id: str, path: str | Path) -> None:
        p = Path(path)
        with self._lock:
            self._map[file_id] = p

    def get(self, file_id: str) -> Optional[Path]:
        with self._lock:
            return self._map.get(file_id)

    def register_avatar(self, sha256: str, path: str | Path) -> None:
        p = Path(path)
        with self._lock:
            self._avatars[sha256] = p

    def get_avatar(self, sha256: str) -> Optional[Path]:
        with self._lock:
            return self._avatars.get(sha256)


class _Handler(BaseHTTPRequestHandler):
    server: "FileHttpServer"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api("GET", parsed)
            return
        if parsed.path.startswith("/f/"):
            file_id = parsed.path.replace("/f/", "", 1).strip("/")
            path = self.server.registry.get(file_id)
            download_name = path.name if path else "download.bin"
        elif parsed.path.startswith("/avatar/"):
            sha256 = parsed.path.replace("/avatar/", "", 1).strip("/")
            path = self.server.registry.get_avatar(sha256)
            download_name = f"avatar_{sha256}.png"
        else:
            self.send_error(404)
            return
        if not path or not path.exists():
            self.send_error(404)
            return
        try:
            size = path.stat().st_size
            mime, _ = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
            self.end_headers()
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(1024 * 256)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except Exception:
            try:
                self.send_error(500)
            except Exception:
                pass

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api("POST", parsed)
            return
        self.send_error(405)

    def do_OPTIONS(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "http://localhost")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Token")
            self.end_headers()
            return
        self.send_error(405)

    def _handle_api(self, method: str, parsed: urllib.parse.ParseResult) -> None:
        api_service = self.server.api_service
        if not api_service or not self.server.api_enabled:
            self.send_error(404)
            return
        if not _is_localhost(self.client_address[0]):
            self.send_error(403)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else b""
        status, payload, content_type = api_service.handle(
            method,
            parsed.path,
            parsed.query,
            body,
            {k: v for k, v in self.headers.items()},
            self.server.server_address[1],
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "http://localhost")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - signature
        return


class FileHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        registry: FileRegistry,
        api_service: ApiService | None,
        api_enabled: bool,
    ) -> None:
        super().__init__(server_address, _Handler)
        self.registry = registry
        self.api_service = api_service
        self.api_enabled = api_enabled


class FileServer:
    def __init__(self, port_range: tuple[int, int] = (51338, 51388)) -> None:
        self._registry = FileRegistry()
        self._server: FileHttpServer | None = None
        self._thread: threading.Thread | None = None
        self._port_range = port_range
        self._api_service: ApiService | None = None
        self._api_enabled = True

    @property
    def port(self) -> int:
        if self._server:
            return self._server.server_address[1]
        return 0

    def ensure_running(self) -> int:
        if self._server:
            return self.port
        for port in range(self._port_range[0], self._port_range[1] + 1):
            try:
                self._server = FileHttpServer(
                    ("0.0.0.0", port),
                    self._registry,
                    self._api_service,
                    self._api_enabled,
                )
                break
            except OSError:
                continue
        if not self._server:
            return 0

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.port

    def register_file(self, file_id: str, path: str) -> None:
        self._registry.register(file_id, path)

    def register_avatar(self, sha256: str, path: str) -> None:
        self._registry.register_avatar(sha256, path)

    def set_api_service(self, service: ApiService | None) -> None:
        self._api_service = service
        if self._server:
            self._server.api_service = service

    def set_api_enabled(self, enabled: bool) -> None:
        self._api_enabled = enabled
        if self._server:
            self._server.api_enabled = enabled

    def shutdown(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None


def _is_localhost(addr: str) -> bool:
    return addr in {"127.0.0.1", "::1"}
