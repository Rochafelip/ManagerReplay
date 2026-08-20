import re
from pathlib import Path


def build_camera_dir(storage_root: Path, mode: str, n_cameras: int, camera_id: int) -> Path:
    camera_dir = storage_root / mode / str(n_cameras) / f"camera-{camera_id}"
    camera_dir.mkdir(parents=True, exist_ok=True)
    return camera_dir


def save_chunk(camera_dir: Path, session_id: str, part_number: int, data: bytes) -> Path:
    safe_session_id = re.sub(r"[^A-Za-z0-9_-]", "", session_id)
    chunk_path = camera_dir / f"{safe_session_id}_parte{part_number}.webm"
    chunk_path.write_bytes(data)
    return chunk_path
