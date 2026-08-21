import http.client
import json
import ssl
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from server import chunks_receiver


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


def _start_server(tmp_path, cert_path, key_path, storage_root=None):
    storage_root = storage_root or (tmp_path / "storage")
    static_dir = tmp_path / "static"
    static_dir.mkdir(exist_ok=True)
    events_file = tmp_path / "events.jsonl"

    server = chunks_receiver.build_server(
        storage_root=storage_root,
        n_cameras=2,
        static_dir=static_dir,
        cert_path=cert_path,
        key_path=key_path,
        events_file=events_file,
        host="127.0.0.1",
        port=0,
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    return server, thread, port


def _https_connection(port):
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return http.client.HTTPSConnection("127.0.0.1", port, context=ssl_context)


def test_chunks_receiver_writes_posted_chunk_to_disk(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)

    try:
        conn = _https_connection(port)
        conn.request("POST", "/upload?camera=1&session=2026-08-20T18-32-10&part=1", body=b"fake-video-bytes")
        response = conn.getresponse()
        assert response.status == 204
    finally:
        server.shutdown()
        thread.join(timeout=2)

    written = storage_root / "2026-08-20" / "camera1_2026-08-20T18-32-10_parte1.webm"
    assert written.read_bytes() == b"fake-video-bytes"


def test_files_route_serves_recordings_from_storage_root(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    camera_dir = storage_root / "camera-1"
    camera_dir.mkdir(parents=True)
    (camera_dir / "chunk-0000.webm").write_bytes(b"video-bytes")

    server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)

    try:
        conn = _https_connection(port)
        conn.request("GET", "/files/camera-1/chunk-0000.webm")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        assert body == b"video-bytes"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_files_route_streams_merged_recording_when_parts_exist(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    day_dir = storage_root / "2026-08-20"
    day_dir.mkdir(parents=True)
    (day_dir / "camera2_2026-08-20T18-32-10_parte1.webm").write_bytes(b"parte-um-")
    (day_dir / "camera2_2026-08-20T18-32-10_parte2.webm").write_bytes(b"parte-dois")

    server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)

    try:
        conn = _https_connection(port)
        conn.request("GET", "/files/2026-08-20/camera2_2026-08-20T18-32-10.webm")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        assert body == b"parte-um-parte-dois"
        assert response.getheader("Content-Type") == "video/webm"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_files_route_returns_404_for_merged_name_with_no_matching_parts(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    (storage_root / "2026-08-20").mkdir(parents=True)

    server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)

    try:
        conn = _https_connection(port)
        conn.request("GET", "/files/2026-08-20/camera2_nope.webm")
        response = conn.getresponse()
        response.read()
        assert response.status == 404
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_files_route_still_serves_a_literal_file_matching_merged_name_pattern(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    day_dir = storage_root / "2026-08-20"
    day_dir.mkdir(parents=True)
    (day_dir / "camera2_2026-08-20T18-32-10.webm").write_bytes(b"already-merged-file")

    server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)

    try:
        conn = _https_connection(port)
        conn.request("GET", "/files/2026-08-20/camera2_2026-08-20T18-32-10.webm")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        assert body == b"already-merged-file"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_files_html_page_is_served_from_static_dir_not_storage_root(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "files.html").write_text("<html>explorer page</html>")

    server, thread, port = _start_server(tmp_path, cert_path, key_path)

    try:
        conn = _https_connection(port)
        conn.request("GET", "/files.html")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        assert body == b"<html>explorer page</html>"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_events_route_records_lance_and_returns_it(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    server, thread, port = _start_server(tmp_path, cert_path, key_path)

    try:
        conn = _https_connection(port)
        conn.request("POST", "/events?camera=1")
        response = conn.getresponse()
        body = json.loads(response.read())
        assert response.status == 200
        assert body["nome"] == "LanceEpico 001"
        assert body["camera"] == "1"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_files_list_route_returns_directory_entries(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    (storage_root / "chunks").mkdir(parents=True)
    (storage_root / "chunks" / "chunk-0000.webm").write_bytes(b"1234")

    server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)

    try:
        conn = _https_connection(port)
        conn.request("GET", "/files-list?path=chunks")
        response = conn.getresponse()
        body = json.loads(response.read())
        assert response.status == 200
        assert body == [{"name": "chunk-0000.webm", "is_dir": False, "size": 4, "mtime": body[0]["mtime"]}]
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_session_start_then_recording_status_lists_it(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    server, thread, port = _start_server(tmp_path, cert_path, key_path)

    try:
        conn = _https_connection(port)
        conn.request("POST", "/session-start?camera=1&name=Carlos&quality=hd30")
        start_response = conn.getresponse()
        start_response.read()
        assert start_response.status == 204

        conn = _https_connection(port)
        conn.request("GET", "/recording-status")
        response = conn.getresponse()
        body = json.loads(response.read())
        assert response.status == 200
        assert len(body) == 1
        assert body[0]["camera"] == 1
        assert body[0]["name"] == "Carlos"
        assert body[0]["quality"] == "hd30"
        assert body[0]["chunks_received"] == 0
        assert body[0]["seconds_since_last_chunk"] is None
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_session_stop_removes_it_from_recording_status(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    server, thread, port = _start_server(tmp_path, cert_path, key_path)

    try:
        conn = _https_connection(port)
        conn.request("POST", "/session-start?camera=1&name=Carlos&quality=hd30")
        conn.getresponse().read()

        conn = _https_connection(port)
        conn.request("POST", "/session-stop?camera=1")
        stop_response = conn.getresponse()
        stop_response.read()
        assert stop_response.status == 204

        conn = _https_connection(port)
        conn.request("GET", "/recording-status")
        body = json.loads(conn.getresponse().read())
        assert body == []
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_upload_updates_chunk_count_for_active_session(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    server, thread, port = _start_server(tmp_path, cert_path, key_path)

    try:
        conn = _https_connection(port)
        conn.request("POST", "/session-start?camera=1&name=Carlos&quality=hd30")
        conn.getresponse().read()

        conn = _https_connection(port)
        conn.request("POST", "/upload?camera=1&session=2026-08-20T18-32-10&part=1", body=b"fake-video-bytes")
        conn.getresponse().read()

        conn = _https_connection(port)
        conn.request("GET", "/recording-status")
        body = json.loads(conn.getresponse().read())
        assert body[0]["chunks_received"] == 1
        assert body[0]["bytes_received"] == len(b"fake-video-bytes")
        assert body[0]["seconds_since_last_chunk"] == 0
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_monitor_status_route_returns_live_reading_plus_disk_usage(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    fake_status = {
        "timestamp": "2026-08-20 18:00:00",
        "cpu_pct": 8.2,
        "ram_used_mb": 164,
        "ram_total_mb": 955,
        "temp_c": 41.3,
        "arm_clock_mhz": 700,
        "core_clock_mhz": 275,
        "undervoltage_now": False,
        "freq_capped_now": False,
        "throttled_now": False,
        "undervoltage_ever": False,
    }

    with patch("server.chunks_receiver.read_live_status", return_value=fake_status):
        server, thread, port = _start_server(tmp_path, cert_path, key_path)
        try:
            conn = _https_connection(port)
            conn.request("GET", "/monitor-status")
            response = conn.getresponse()
            body = json.loads(response.read())
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert response.status == 200
    assert body["cpu_pct"] == 8.2
    assert body["temp_c"] == 41.3
    assert body["undervoltage_now"] is False
    assert body["disk_total_mb"] > 0
    assert body["disk_used_mb"] >= 0


def test_monitor_status_route_returns_503_when_measurement_fails(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert

    with patch("server.chunks_receiver.read_live_status", side_effect=FileNotFoundError("vcgencmd not found")):
        server, thread, port = _start_server(tmp_path, cert_path, key_path)
        try:
            conn = _https_connection(port)
            conn.request("GET", "/monitor-status")
            response = conn.getresponse()
            response.read()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert response.status == 503
