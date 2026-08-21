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
        assert body["nome"] == "Lance Epico 001"
        assert body["camera"] == "1"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_events_list_route_returns_recorded_events(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    server, thread, port = _start_server(tmp_path, cert_path, key_path)

    try:
        conn = _https_connection(port)
        conn.request("POST", "/events?camera=1")
        conn.getresponse().read()

        conn = _https_connection(port)
        conn.request("GET", "/events-list")
        response = conn.getresponse()
        body = json.loads(response.read())
        assert response.status == 200
        assert len(body) == 1
        assert body[0]["nome"] == "Lance Epico 001"
        assert body[0]["camera"] == "1"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_lance_clip_route_saves_uploaded_clip_under_lances_subfolder(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)

    try:
        conn = _https_connection(port)
        conn.request(
            "POST",
            "/lance-clip?camera=2&nome=LanceEpico+001",
            body=b"clip-bytes",
        )
        response = conn.getresponse()
        response.read()
        assert response.status == 204
    finally:
        server.shutdown()
        thread.join(timeout=2)

    saved = list(storage_root.glob("*/lances/lance_camera2_LanceEpico001.webm"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"clip-bytes"


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
        assert body == [{
            "name": "chunk-0000.webm",
            "is_dir": False,
            "size": 4,
            "mtime": body[0]["mtime"],
            "duration_seconds": None,
        }]
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

    fake_external_storage = [{"device": "/dev/sda1", "mountpoint": "/media/rocha/SSD1", "fstype": "ext4", "total_mb": 60000, "free_mb": 40000}]

    with patch("server.chunks_receiver.read_live_status", return_value=fake_status), \
         patch("server.chunks_receiver.detect_external_storage", return_value=fake_external_storage):
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
    assert body["external_storage"] == fake_external_storage


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


def test_storage_options_lists_default_and_detected_external_drives(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    fake_external = [{"device": "/dev/sda1", "mountpoint": "/media/hd1", "fstype": "exfat", "total_mb": 2000000, "free_mb": 1000000}]

    with patch("server.chunks_receiver.detect_external_storage", return_value=fake_external):
        server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)
        try:
            conn = _https_connection(port)
            conn.request("GET", "/storage-options")
            response = conn.getresponse()
            body = json.loads(response.read())
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert response.status == 200
    assert body["current"] == str(storage_root)
    paths = [o["path"] for o in body["options"]]
    assert str(storage_root) in paths
    assert "/media/hd1" in paths


def test_storage_select_switches_where_new_uploads_are_saved(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    external_mount = tmp_path / "media" / "hd1"
    external_mount.mkdir(parents=True)
    fake_external = [{"device": "/dev/sda1", "mountpoint": str(external_mount), "fstype": "exfat", "total_mb": 2000000, "free_mb": 1000000}]

    with patch("server.chunks_receiver.detect_external_storage", return_value=fake_external):
        server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)
        try:
            conn = _https_connection(port)
            conn.request("POST", f"/storage-select?path={external_mount}")
            select_response = conn.getresponse()
            select_response.read()
            assert select_response.status == 204

            conn = _https_connection(port)
            conn.request("POST", "/upload?camera=1&session=2026-08-21T10-00-00&part=1", body=b"after-switch")
            conn.getresponse().read()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    written = external_mount / "managerreplay-recordings" / "2026-08-21" / "camera1_2026-08-21T10-00-00_parte1.webm"
    assert written.read_bytes() == b"after-switch"
    assert not (storage_root / "2026-08-21").exists()


def test_storage_select_rejects_unknown_path(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert

    with patch("server.chunks_receiver.detect_external_storage", return_value=[]):
        server, thread, port = _start_server(tmp_path, cert_path, key_path)
        try:
            conn = _https_connection(port)
            conn.request("POST", "/storage-select?path=/nope/not-a-real-option")
            response = conn.getresponse()
            response.read()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert response.status == 400


def test_storage_select_rejects_switch_while_a_camera_is_recording(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    external_mount = tmp_path / "media" / "hd1"
    external_mount.mkdir(parents=True)
    fake_external = [{"device": "/dev/sda1", "mountpoint": str(external_mount), "fstype": "exfat", "total_mb": 2000000, "free_mb": 1000000}]

    with patch("server.chunks_receiver.detect_external_storage", return_value=fake_external):
        server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)
        try:
            conn = _https_connection(port)
            conn.request("POST", "/session-start?camera=1&name=Carlos&quality=hd30")
            conn.getresponse().read()

            conn = _https_connection(port)
            conn.request("POST", f"/storage-select?path={external_mount}")
            response = conn.getresponse()
            response.read()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert response.status == 409


def test_storage_eject_syncs_and_unmounts_the_device(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    external_mount = tmp_path / "media" / "hd1"
    external_mount.mkdir(parents=True)
    fake_external = [{"device": "/dev/sda1", "mountpoint": str(external_mount), "fstype": "exfat", "total_mb": 2000000, "free_mb": 1000000}]

    with patch("server.chunks_receiver.detect_external_storage", return_value=fake_external), \
         patch("server.chunks_receiver.subprocess.run") as mock_run:
        server, thread, port = _start_server(tmp_path, cert_path, key_path)
        try:
            conn = _https_connection(port)
            conn.request("POST", f"/storage-eject?path={external_mount}")
            response = conn.getresponse()
            response.read()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert response.status == 204
    commands = [call.args[0] for call in mock_run.call_args_list]
    assert ["sync"] in commands
    assert any(cmd[:2] == ["sudo", "umount"] and str(external_mount) in cmd for cmd in commands)


def test_storage_eject_switches_back_to_default_when_ejecting_the_active_drive(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    external_mount = tmp_path / "media" / "hd1"
    external_mount.mkdir(parents=True)
    fake_external = [{"device": "/dev/sda1", "mountpoint": str(external_mount), "fstype": "exfat", "total_mb": 2000000, "free_mb": 1000000}]

    with patch("server.chunks_receiver.detect_external_storage", return_value=fake_external), \
         patch("server.chunks_receiver.subprocess.run"):
        server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)
        try:
            conn = _https_connection(port)
            conn.request("POST", f"/storage-select?path={external_mount}")
            conn.getresponse().read()

            conn = _https_connection(port)
            conn.request("POST", f"/storage-eject?path={external_mount}")
            conn.getresponse().read()

            conn = _https_connection(port)
            conn.request("POST", "/upload?camera=1&session=2026-08-21T10-00-00&part=1", body=b"after-eject")
            conn.getresponse().read()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    written = storage_root / "2026-08-21" / "camera1_2026-08-21T10-00-00_parte1.webm"
    assert written.read_bytes() == b"after-eject"


def test_storage_eject_rejects_unknown_mountpoint(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert

    with patch("server.chunks_receiver.detect_external_storage", return_value=[]):
        server, thread, port = _start_server(tmp_path, cert_path, key_path)
        try:
            conn = _https_connection(port)
            conn.request("POST", "/storage-eject?path=/nope/not-mounted")
            response = conn.getresponse()
            response.read()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert response.status == 400


def test_storage_eject_rejects_while_a_camera_is_recording(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    external_mount = tmp_path / "media" / "hd1"
    external_mount.mkdir(parents=True)
    fake_external = [{"device": "/dev/sda1", "mountpoint": str(external_mount), "fstype": "exfat", "total_mb": 2000000, "free_mb": 1000000}]

    with patch("server.chunks_receiver.detect_external_storage", return_value=fake_external):
        server, thread, port = _start_server(tmp_path, cert_path, key_path)
        try:
            conn = _https_connection(port)
            conn.request("POST", "/session-start?camera=1&name=Carlos&quality=hd30")
            conn.getresponse().read()

            conn = _https_connection(port)
            conn.request("POST", f"/storage-eject?path={external_mount}")
            response = conn.getresponse()
            response.read()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert response.status == 409


def test_storage_eject_returns_500_when_unmount_fails(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    external_mount = tmp_path / "media" / "hd1"
    external_mount.mkdir(parents=True)
    fake_external = [{"device": "/dev/sda1", "mountpoint": str(external_mount), "fstype": "exfat", "total_mb": 2000000, "free_mb": 1000000}]

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["sudo", "umount"]:
            raise subprocess.CalledProcessError(1, cmd, stderr="target is busy")
        return subprocess.CompletedProcess(cmd, 0)

    with patch("server.chunks_receiver.detect_external_storage", return_value=fake_external), \
         patch("server.chunks_receiver.subprocess.run", side_effect=fake_run):
        server, thread, port = _start_server(tmp_path, cert_path, key_path)
        try:
            conn = _https_connection(port)
            conn.request("POST", f"/storage-eject?path={external_mount}")
            response = conn.getresponse()
            response.read()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert response.status == 500
