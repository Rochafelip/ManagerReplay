from pathlib import Path

from server.storage import build_day_dir, find_session_parts, sanitize_lance_name, save_chunk, save_lance_clip


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


def test_find_session_parts_returns_paths_sorted_by_part_number(tmp_path: Path):
    save_chunk(tmp_path, camera_id=2, session_id="2026-08-20T18-32-10", part_number=2, data=b"b")
    save_chunk(tmp_path, camera_id=2, session_id="2026-08-20T18-32-10", part_number=1, data=b"a")
    save_chunk(tmp_path, camera_id=2, session_id="2026-08-20T18-32-10", part_number=10, data=b"j")
    save_chunk(tmp_path, camera_id=1, session_id="2026-08-20T18-32-10", part_number=1, data=b"other-camera")

    parts = find_session_parts(tmp_path, camera_id="2", session_id="2026-08-20T18-32-10")

    assert [p.name for p in parts] == [
        "camera2_2026-08-20T18-32-10_parte1.webm",
        "camera2_2026-08-20T18-32-10_parte2.webm",
        "camera2_2026-08-20T18-32-10_parte10.webm",
    ]


def test_find_session_parts_returns_empty_list_when_none_match(tmp_path: Path):
    assert find_session_parts(tmp_path, camera_id="1", session_id="nope") == []


def test_sanitize_lance_name_strips_spaces_and_punctuation():
    assert sanitize_lance_name("LanceEpico 001") == "LanceEpico001"
    assert sanitize_lance_name("Gol! do Time (2º)") == "GoldoTime2"


def test_save_lance_clip_writes_file_under_lances_subfolder(tmp_path: Path):
    path = save_lance_clip(tmp_path, camera_id="2", nome="LanceEpico 001", data=b"clip-bytes")

    assert path == tmp_path / "lances" / "lance_camera2_LanceEpico001.webm"
    assert path.read_bytes() == b"clip-bytes"


def test_save_lance_clip_creates_lances_subfolder_if_missing(tmp_path: Path):
    day_dir = tmp_path / "2026-08-21"
    day_dir.mkdir()

    path = save_lance_clip(day_dir, camera_id="1", nome="LanceEpico 002", data=b"x")

    assert path.parent.is_dir()
    assert path.parent.name == "lances"
