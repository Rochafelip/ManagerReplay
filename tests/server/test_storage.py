from pathlib import Path

from server.storage import build_camera_dir, save_chunk


def test_build_camera_dir_creates_nested_path(tmp_path: Path):
    result = build_camera_dir(tmp_path, mode="chunks", n_cameras=2, camera_id=1)

    assert result == tmp_path / "chunks" / "2" / "camera-1"
    assert result.is_dir()


def test_build_camera_dir_is_idempotent(tmp_path: Path):
    first = build_camera_dir(tmp_path, mode="webrtc", n_cameras=1, camera_id=1)
    second = build_camera_dir(tmp_path, mode="webrtc", n_cameras=1, camera_id=1)

    assert first == second
    assert first.is_dir()


def test_save_chunk_writes_file_with_zero_padded_sequence(tmp_path: Path):
    path = save_chunk(tmp_path, sequence_number=3, data=b"fake-video-bytes")

    assert path == tmp_path / "chunk-0003.webm"
    assert path.read_bytes() == b"fake-video-bytes"


def test_save_chunk_handles_sequence_above_9999(tmp_path: Path):
    path = save_chunk(tmp_path, sequence_number=12345, data=b"x")

    assert path == tmp_path / "chunk-12345.webm"
