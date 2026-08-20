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
