import http.client
import ssl
import subprocess
import threading
import time
from pathlib import Path

import pytest

from spikes.spike2 import chunks_receiver


@pytest.fixture
def self_signed_cert(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key_path), "-out", str(cert_path),
            "-days", "1", "-nodes", "-subj", "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )
    return cert_path, key_path


def test_chunks_receiver_writes_posted_chunk_to_disk(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    static_dir = tmp_path / "static"
    static_dir.mkdir()

    server = chunks_receiver.build_server(
        storage_root=storage_root,
        n_cameras=2,
        static_dir=static_dir,
        cert_path=cert_path,
        key_path=key_path,
        host="127.0.0.1",
        port=0,
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)

    try:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        conn = http.client.HTTPSConnection("127.0.0.1", port, context=ssl_context)
        conn.request("POST", "/upload?camera=1&seq=3", body=b"fake-video-bytes")
        response = conn.getresponse()
        assert response.status == 204
    finally:
        server.shutdown()
        thread.join(timeout=2)

    written = storage_root / "chunks" / "2" / "camera-1" / "chunk-0003.webm"
    assert written.read_bytes() == b"fake-video-bytes"


def test_files_route_serves_recordings_from_storage_root(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    camera_dir = storage_root / "chunks" / "1" / "camera-1"
    camera_dir.mkdir(parents=True)
    (camera_dir / "chunk-0000.webm").write_bytes(b"video-bytes")

    server = chunks_receiver.build_server(
        storage_root=storage_root,
        n_cameras=1,
        static_dir=static_dir,
        cert_path=cert_path,
        key_path=key_path,
        host="127.0.0.1",
        port=0,
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)

    try:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        conn = http.client.HTTPSConnection("127.0.0.1", port, context=ssl_context)
        conn.request("GET", "/files/chunks/1/camera-1/chunk-0000.webm")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        assert body == b"video-bytes"
    finally:
        server.shutdown()
        thread.join(timeout=2)
