from __future__ import annotations

import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional


class FileRegistry:
    def __init__(self) -> None:
        self._map: dict[str, Path] = {}
        self._lock = threading.Lock()

    def register(self, file_id: str, path: str | Path) -> None:
        p = Path(path)
        with self._lock:
            self._map[file_id] = p

    def get(self, file_id: str) -> Optional[Path]:
        with self._lock:
            return self._map.get(file_id)


class _Handler(BaseHTTPRequestHandler):
    server: "FileHttpServer"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if not self.path.startswith("/f/"):
            self.send_error(404)
            return
        file_id = self.path.replace("/f/", "", 1).strip("/")
        path = self.server.registry.get(file_id)
        if not path or not path.exists():
            self.send_error(404)
            return
        try:
            size = path.stat().st_size
            mime, _ = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
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

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - signature
        return


class FileHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], registry: FileRegistry) -> None:
        super().__init__(server_address, _Handler)
        self.registry = registry


class FileServer:
    def __init__(self, port_range: tuple[int, int] = (51338, 51388)) -> None:
        self._registry = FileRegistry()
        self._server: FileHttpServer | None = None
        self._thread: threading.Thread | None = None
        self._port_range = port_range

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
                self._server = FileHttpServer(("0.0.0.0", port), self._registry)
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

    def shutdown(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
