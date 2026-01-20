from __future__ import annotations

import io
import random
import socket
import struct
import threading
import urllib.request
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from pathlib import Path

from config_store import ConfigStore
from net import protocol
from net.discovery import DiscoveryTracker
from net.http_fileserver import FileServer
from net.message_store import DedupCache
from util.paths import avatar_cache_path


class MulticastListener(QThread):
    message_received = Signal(dict, str)

    def __init__(self, sock: socket.socket) -> None:
        super().__init__()
        self._sock = sock
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(65536)
            except socket.timeout:
                continue
            except OSError:
                break

            msg = protocol.parse_message(data)
            if msg:
                sender_ip = addr[0]
                self.message_received.emit(msg, sender_ip)

    def stop(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except Exception:
            pass
        self.wait(500)


class MulticastClient(QObject):
    message_received = Signal(dict, str)

    def __init__(self) -> None:
        super().__init__()
        self._send_sock = _create_send_socket()
        self._recv_sock = _create_recv_socket()
        self._listener = MulticastListener(self._recv_sock)
        self._listener.message_received.connect(self.message_received)
        self._listener.start()
        self._lock = threading.Lock()

    def send(self, payload: dict[str, Any]) -> None:
        data = protocol.encode_message(payload)
        if not data:
            return
        with self._lock:
            try:
                self._send_sock.sendto(data, (protocol.MULTICAST_GROUP, protocol.UDP_PORT))
            except Exception:
                pass

    def close(self) -> None:
        try:
            self._listener.stop()
        except Exception:
            pass
        try:
            self._send_sock.close()
        except Exception:
            pass


class AvatarDownloadWorker(QThread):
    finished = Signal(str, str, str)
    failed = Signal(str, str)

    def __init__(self, url: str, dest_path: str, sender_id: str, avatar_sha: str) -> None:
        super().__init__()
        self._url = url
        self._dest_path = dest_path
        self._sender_id = sender_id
        self._avatar_sha = avatar_sha

    def run(self) -> None:
        try:
            with urllib.request.urlopen(self._url, timeout=6) as resp:
                data = resp.read()
            if not data:
                raise ValueError("empty avatar response")
            try:
                from PIL import Image
            except Exception as exc:  # pragma: no cover - pillow missing
                raise RuntimeError("Pillow unavailable") from exc
            image = Image.open(io.BytesIO(data))
            image = image.convert("RGBA")
            Path(self._dest_path).parent.mkdir(parents=True, exist_ok=True)
            image.save(self._dest_path, format="PNG")
            self.finished.emit(self._sender_id, self._avatar_sha, self._dest_path)
        except Exception:
            self.failed.emit(self._sender_id, self._avatar_sha)


class LanChatNetwork(QObject):
    hello_received = Signal(dict, str)
    chat_received = Signal(dict, str)
    file_received = Signal(dict, str)
    online_count = Signal(int)
    avatar_updated = Signal(str, str)

    def __init__(self, store: ConfigStore) -> None:
        super().__init__()
        self._store = store
        self._client = MulticastClient()
        self._client.message_received.connect(self._on_message)
        self._discovery = DiscoveryTracker()
        self._discovery.updated.connect(self.online_count)
        self._file_server = FileServer()
        self._dedup = DedupCache()
        self._http_port = 0
        self._avatar_fetching: set[str] = set()
        self._avatar_workers: list[AvatarDownloadWorker] = []

        self._hello_timer = QTimer(self)
        self._hello_timer.timeout.connect(self.send_hello)
        self._hello_timer.start(2000)

        self._prune_timer = QTimer(self)
        self._prune_timer.timeout.connect(self._prune)
        self._prune_timer.start(2000)

        self._discovery.update_hello(
            protocol.build_hello(
                self._store.config.sender_id,
                self._store.config.user_name,
                self._store.config.avatar_sha256,
                self._http_port,
            ),
            _get_local_ip(),
        )
        QTimer.singleShot(300, self.send_hello)

    def send_hello(self) -> None:
        if self._store.config.avatar_path and self._store.config.avatar_sha256:
            port = self._file_server.ensure_running()
            if port:
                self._http_port = port
                self._file_server.register_avatar(
                    self._store.config.avatar_sha256,
                    self._store.config.avatar_path,
                )
        msg = protocol.build_hello(
            self._store.config.sender_id,
            self._store.config.user_name,
            self._store.config.avatar_sha256,
            self._http_port,
        )
        self._client.send(msg)

    def send_chat(self, text: str) -> dict[str, Any]:
        msg = protocol.build_chat(
            self._store.config.sender_id,
            self._store.config.user_name,
            self._store.config.avatar_sha256,
            text,
        )
        self._send_with_retries(msg)
        return msg

    def send_file(self, file_id: str, file_path: str, filename: str, size: int, sha256: str) -> dict[str, Any]:
        port = self._file_server.ensure_running()
        if not port:
            raise RuntimeError("No free HTTP port available")
        if port != self._http_port:
            self._http_port = port
            self.send_hello()
        self._file_server.register_file(file_id, file_path)
        ip = _get_local_ip()
        url = f"http://{ip}:{self._http_port}/f/{file_id}"
        msg = protocol.build_file(
            self._store.config.sender_id,
            self._store.config.user_name,
            self._store.config.avatar_sha256,
            file_id,
            filename,
            size,
            sha256,
            url,
        )
        self._send_with_retries(msg)
        return msg

    def _send_with_retries(self, msg: dict[str, Any]) -> None:
        self._client.send(msg)
        for delay in (60, 120):
            jitter = random.randint(0, 40)
            QTimer.singleShot(delay + jitter, lambda m=msg: self._client.send(m))

    def _maybe_fetch_avatar(self, msg: dict[str, Any], sender_ip: str) -> None:
        avatar_sha = msg.get("avatar_sha256") or ""
        if not avatar_sha:
            return
        http_port = int(msg.get("http_port") or 0)
        if http_port <= 0:
            return
        cached_path = avatar_cache_path(avatar_sha)
        if cached_path.exists() or avatar_sha in self._avatar_fetching:
            return
        sender_id = msg.get("sender_id") or ""
        if not sender_id:
            return
        url = f"http://{sender_ip}:{http_port}/avatar/{avatar_sha}"
        worker = AvatarDownloadWorker(url, str(cached_path), sender_id, avatar_sha)
        worker.finished.connect(self._on_avatar_fetched)
        worker.failed.connect(self._on_avatar_failed)
        self._avatar_fetching.add(avatar_sha)
        self._avatar_workers.append(worker)
        worker.start()

    def _on_avatar_fetched(self, sender_id: str, avatar_sha: str, path: str) -> None:
        self._avatar_fetching.discard(avatar_sha)
        self._avatar_workers = [w for w in self._avatar_workers if w.isRunning()]
        self.avatar_updated.emit(sender_id, avatar_sha)

    def _on_avatar_failed(self, sender_id: str, avatar_sha: str) -> None:
        self._avatar_fetching.discard(avatar_sha)
        self._avatar_workers = [w for w in self._avatar_workers if w.isRunning()]

    def _on_message(self, msg: dict[str, Any], sender_ip: str) -> None:
        msg_type = msg.get("t")
        if msg_type == "HELLO":
            self._discovery.update_hello(msg, sender_ip)
            self.hello_received.emit(msg, sender_ip)
            self._maybe_fetch_avatar(msg, sender_ip)
            return

        message_id = msg.get("message_id")
        if not message_id:
            return
        sender_id = msg.get("sender_id")
        if sender_id == self._store.config.sender_id:
            return
        if self._dedup.seen(message_id):
            return

        if msg_type == "CHAT":
            self.chat_received.emit(msg, sender_ip)
        elif msg_type == "FILE":
            self.file_received.emit(msg, sender_ip)

    def _prune(self) -> None:
        self._discovery.prune(8)

    def shutdown(self) -> None:
        try:
            self._hello_timer.stop()
            self._prune_timer.stop()
        except Exception:
            pass
        self._client.close()
        self._file_server.shutdown()


def _get_local_ip() -> str:
    ip = "127.0.0.1"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((protocol.MULTICAST_GROUP, protocol.UDP_PORT))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        try:
            s.close()
        except Exception:
            pass

    if ip.startswith("127.") or ip == "0.0.0.0":
        try:
            candidates = socket.gethostbyname_ex(socket.gethostname())[2]
            for cand in candidates:
                if not cand.startswith("127."):
                    ip = cand
                    break
        except Exception:
            pass
    return ip


def _create_send_socket() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack("b", protocol.TTL))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    return sock


def _create_recv_socket() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", protocol.UDP_PORT))
    except OSError:
        sock.bind((protocol.MULTICAST_GROUP, protocol.UDP_PORT))

    mreq = struct.pack("4s4s", socket.inet_aton(protocol.MULTICAST_GROUP), socket.inet_aton("0.0.0.0"))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(0.5)
    return sock
