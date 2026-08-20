from pathlib import Path

from server.storage import build_day_dir, save_chunk


def test_build_day_dir_creates_path_from_session_id_date(tmp_path: Path):
    result = build_day_dir(tmp_path, session_id="2026-08-20T18-32-10-123Z")

    assert result == tmp_path / "2026-08-20"
    assert result.is_dir()


def test_build_day_dir_is_idempotent(tmp_path: Path):
    first = build_day_dir(tmp_path, session_id="2026-08-20T18-32-10-123Z")
    second = build_day_dir(tmp_path, session_id="2026-08-20T19-05-00-000Z")

    assert first == second
    assert first.is_dir()


def test_save_chunk_names_file_by_camera_session_and_part(tmp_path: Path):
    path = save_chunk(tmp_path, camera_id=1, session_id="2026-08-20T18-32-10", part_number=1, data=b"fake-video-bytes")

    assert path == tmp_path / "camera1_2026-08-20T18-32-10_parte1.webm"
    assert path.read_bytes() == b"fake-video-bytes"


def test_save_chunk_handles_double_digit_parts(tmp_path: Path):
    path = save_chunk(tmp_path, camera_id=2, session_id="2026-08-20T18-32-10", part_number=12, data=b"x")

    assert path == tmp_path / "camera2_2026-08-20T18-32-10_parte12.webm"


def test_save_chunk_sanitizes_unsafe_session_id(tmp_path: Path):
    path = save_chunk(tmp_path, camera_id=1, session_id="../../etc/passwd", part_number=1, data=b"x")

    assert path.parent == tmp_path
    assert "/" not in path.name and ".." not in path.name
