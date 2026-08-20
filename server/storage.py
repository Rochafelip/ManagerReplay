from pathlib import Path


def build_camera_dir(storage_root: Path, mode: str, n_cameras: int, camera_id: int) -> Path:
    camera_dir = storage_root / mode / str(n_cameras) / f"camera-{camera_id}"
    camera_dir.mkdir(parents=True, exist_ok=True)
    return camera_dir


def save_chunk(camera_dir: Path, sequence_number: int, data: bytes) -> Path:
    chunk_path = camera_dir / f"chunk-{sequence_number:04d}.webm"
    chunk_path.write_bytes(data)
    return chunk_path
