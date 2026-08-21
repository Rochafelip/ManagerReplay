from pathlib import Path

import pytest

from server.file_listing import list_directory


def test_list_directory_returns_files_and_dirs(tmp_path: Path):
    (tmp_path / "camera-1").mkdir()
    (tmp_path / "chunk-0000.webm").write_bytes(b"1234")

    entries = list_directory(tmp_path, "")

    names = {e["name"]: e for e in entries}
    assert names["camera-1"]["is_dir"] is True
    assert names["camera-1"]["size"] is None
    assert names["chunk-0000.webm"]["is_dir"] is False
    assert names["chunk-0000.webm"]["size"] == 4


def test_list_directory_resolves_relative_subpath(tmp_path: Path):
    sub = tmp_path / "chunks" / "1"
    sub.mkdir(parents=True)
    (sub / "camera-1").mkdir()

    entries = list_directory(tmp_path, "chunks/1")

    assert entries[0]["name"] == "camera-1"


def test_list_directory_rejects_path_traversal(tmp_path: Path):
    with pytest.raises(ValueError):
        list_directory(tmp_path, "../../etc")


def test_list_directory_missing_path_raises_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        list_directory(tmp_path, "does-not-exist")


def test_list_directory_groups_recording_chunk_parts_into_one_entry(tmp_path: Path):
    (tmp_path / "camera2_2026-08-20T18-32-10_parte1.webm").write_bytes(b"12345")
    (tmp_path / "camera2_2026-08-20T18-32-10_parte2.webm").write_bytes(b"67890")

    entries = list_directory(tmp_path, "")

    assert len(entries) == 1
    assert entries[0]["name"] == "camera2_2026-08-20T18-32-10.webm"
    assert entries[0]["is_dir"] is False
    assert entries[0]["size"] == 10


def test_list_directory_groups_parts_per_camera_and_session_separately(tmp_path: Path):
    (tmp_path / "camera1_2026-08-20T18-32-10_parte1.webm").write_bytes(b"a")
    (tmp_path / "camera2_2026-08-20T18-32-10_parte1.webm").write_bytes(b"bb")

    entries = list_directory(tmp_path, "")

    sizes = {e["name"]: e["size"] for e in entries}
    assert sizes == {
        "camera1_2026-08-20T18-32-10.webm": 1,
        "camera2_2026-08-20T18-32-10.webm": 2,
    }


def test_list_directory_leaves_unmatched_files_and_dirs_untouched(tmp_path: Path):
    (tmp_path / "camera-1").mkdir()
    (tmp_path / "jogo_completo.webm").write_bytes(b"1234")

    entries = list_directory(tmp_path, "")

    names = {e["name"] for e in entries}
    assert names == {"camera-1", "jogo_completo.webm"}


def test_list_directory_does_not_group_lance_clip_files(tmp_path: Path):
    lances_dir = tmp_path / "lances"
    lances_dir.mkdir()
    (lances_dir / "lance_camera2_LanceEpico001.webm").write_bytes(b"clip")

    entries = list_directory(tmp_path, "lances")

    assert entries == [{
        "name": "lance_camera2_LanceEpico001.webm",
        "is_dir": False,
        "size": 4,
        "mtime": entries[0]["mtime"],
    }]
