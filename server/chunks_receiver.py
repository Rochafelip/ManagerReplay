import json
import re
import shutil
import ssl
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from server.events import record_event
from server.file_listing import list_directory
from server.monitor_status import get_disk_usage, read_live_status
from server.sessions import list_sessions, record_chunk, start_session, stop_session
from server.storage import build_day_dir, find_session_parts, save_chunk

# Matches the merged/virtual recording name produced by file_listing
# (e.g. "camera2_2026-08-20T18-32-10.webm"), as opposed to a literal
# "..._parteN.webm" chunk file.
_MERGED_RECORDING_PATTERN = re.compile(r"^camera(\d+)_(.+)\.webm$")


class ChunksUploadHandler(SimpleHTTPRequestHandler):
    storage_root: Path = None
    n_cameras: int = 1
    events_file: Path = None
    sessions_registry: dict = None
    sessions_lock: threading.Lock = None

    def translate_path(self, path):
        if path.startswith("/files/") or path == "/files":
            original_directory = self.directory
            self.directory = str(self.storage_root)
            try:
                return super().translate_path(path[len("/files"):] or "/")
            finally:
                self.directory = original_directory
        return super().translate_path(path)

    def do_GET(self):
        if self.path.startswith("/files-list"):
            self._handle_files_list()
            return
        if self.path.startswith("/monitor-status"):
            self._handle_monitor_status()
            return
        if self.path.startswith("/recording-status"):
            self._handle_recording_status()
            return
        if self.path.startswith("/files/") and self._serve_merged_recording():
            return
        super().do_GET()

    def _serve_merged_recording(self) -> bool:
        """Streams a recording's chunks concatenated as one download, for
        the virtual filenames file_listing groups them under. Returns False
        (falling through to the normal static-file handler) whenever a real
        file already exists at that path, or the name/parts don't match."""
        rel_path = unquote(urlparse(self.path).path[len("/files/"):])
        if (self.storage_root / rel_path).exists():
            return False

        rel = Path(rel_path)
        match = _MERGED_RECORDING_PATTERN.match(rel.name)
        if not match:
            return False

        day_dir = (self.storage_root / rel.parent).resolve()
        storage_root = self.storage_root.resolve()
        if day_dir != storage_root and storage_root not in day_dir.parents:
            return False

        camera_id, session_id = match.group(1), match.group(2)
        parts = find_session_parts(day_dir, camera_id, session_id)
        if not parts:
            return False

        total_size = sum(part.stat().st_size for part in parts)
        self.send_response(200)
        self.send_header("Content-Type", "video/webm")
        self.send_header("Content-Length", str(total_size))
        self.send_header("Content-Disposition", f'attachment; filename="{rel.name}"')
        self.end_headers()
        for part in parts:
            with part.open("rb") as part_file:
                shutil.copyfileobj(part_file, self.wfile)
        return True

    def _handle_recording_status(self):
        with self.sessions_lock:
            sessions = list_sessions(self.sessions_registry, now=time.time())

        body = json.dumps(sessions).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_files_list(self):
        query = parse_qs(urlparse(self.path).query)
        rel_path = query.get("path", [""])[0]
        try:
            entries = list_directory(self.storage_root, rel_path)
        except (ValueError, FileNotFoundError) as err:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(str(err).encode("utf-8"))
            return

        body = json.dumps(entries).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_monitor_status(self):
        try:
            status = read_live_status()
        except (OSError, ValueError) as err:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(str(err).encode("utf-8"))
            return

        status.update(get_disk_usage(self.storage_root))

        body = json.dumps(status).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.startswith("/upload"):
            self._handle_upload()
        elif self.path.startswith("/events"):
            self._handle_event()
        elif self.path.startswith("/session-start"):
            self._handle_session_start()
        elif self.path.startswith("/session-stop"):
            self._handle_session_stop()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_session_start(self):
        query = parse_qs(urlparse(self.path).query)
        try:
            camera_id = int(query["camera"][0])
        except (KeyError, ValueError, IndexError):
            self.send_response(400)
            self.end_headers()
            return
        name = query.get("name", [""])[0]
        quality = query.get("quality", [""])[0]

        with self.sessions_lock:
            start_session(self.sessions_registry, camera_id, name, quality, now=time.time())

        self.send_response(204)
        self.end_headers()

    def _handle_session_stop(self):
        query = parse_qs(urlparse(self.path).query)
        try:
            camera_id = int(query["camera"][0])
        except (KeyError, ValueError, IndexError):
            self.send_response(400)
            self.end_headers()
            return

        with self.sessions_lock:
            stop_session(self.sessions_registry, camera_id)

        self.send_response(204)
        self.end_headers()

    def _handle_upload(self):
        query = parse_qs(urlparse(self.path).query)
        try:
            camera_id = int(query["camera"][0])
            session_id = query["session"][0]
            part_number = int(query["part"][0])
        except (KeyError, ValueError, IndexError):
            self.send_response(400)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)

        day_dir = build_day_dir(self.storage_root, session_id)
        save_chunk(day_dir, camera_id, session_id, part_number, data)

        with self.sessions_lock:
            record_chunk(self.sessions_registry, camera_id, len(data), now=time.time())

        self.send_response(204)
        self.end_headers()

    def _handle_event(self):
        query = parse_qs(urlparse(self.path).query)
        camera_id = query.get("camera", ["?"])[0]

        event = record_event(self.events_file, camera_id)

        body = json.dumps(event).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def build_server(
    storage_root: Path,
    n_cameras: int,
    static_dir: Path,
    cert_path: Path,
    key_path: Path,
    events_file: Path,
    host: str = "0.0.0.0",
    port: int = 8443,
) -> ThreadingHTTPServer:
    ChunksUploadHandler.storage_root = storage_root
    ChunksUploadHandler.n_cameras = n_cameras
    ChunksUploadHandler.events_file = events_file
    ChunksUploadHandler.sessions_registry = {}
    ChunksUploadHandler.sessions_lock = threading.Lock()
    handler = partial(ChunksUploadHandler, directory=str(static_dir))

    server = ThreadingHTTPServer((host, port), handler)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    return server


def run(
    storage_root: Path,
    n_cameras: int,
    static_dir: Path,
    cert_path: Path,
    key_path: Path,
    events_file: Path,
    host: str = "0.0.0.0",
    port: int = 8443,
):
    storage_root.mkdir(parents=True, exist_ok=True)
    server = build_server(
        storage_root, n_cameras, static_dir, cert_path, key_path, events_file, host, port
    )
    print(f"[chunks] listening on https://{host}:{port}, storage={storage_root}")
    server.serve_forever()
