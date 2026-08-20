import json
import ssl
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from server.events import record_event
from server.storage import build_camera_dir, save_chunk


class ChunksUploadHandler(SimpleHTTPRequestHandler):
    storage_root: Path = None
    n_cameras: int = 1
    events_file: Path = None

    def translate_path(self, path):
        if path.startswith("/files"):
            original_directory = self.directory
            self.directory = str(self.storage_root)
            try:
                return super().translate_path(path[len("/files"):] or "/")
            finally:
                self.directory = original_directory
        return super().translate_path(path)

    def do_POST(self):
        if self.path.startswith("/upload"):
            self._handle_upload()
        elif self.path.startswith("/events"):
            self._handle_event()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_upload(self):
        query = parse_qs(urlparse(self.path).query)
        try:
            camera_id = int(query["camera"][0])
            sequence_number = int(query["seq"][0])
        except (KeyError, ValueError, IndexError):
            self.send_response(400)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)

        camera_dir = build_camera_dir(self.storage_root, "chunks", self.n_cameras, camera_id)
        save_chunk(camera_dir, sequence_number, data)

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
    server = build_server(storage_root, n_cameras, static_dir, cert_path, key_path, events_file, host, port)
    print(f"[chunks] listening on https://{host}:{port}, storage={storage_root}")
    server.serve_forever()
