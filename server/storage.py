import re
from pathlib import Path


def build_day_dir(storage_root: Path, session_id: str) -> Path:
    date_part = session_id[:10]
    day_dir = storage_root / date_part
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir


def save_chunk(day_dir: Path, camera_id: int, session_id: str, part_number: int, data: bytes) -> Path:
    safe_session_id = re.sub(r"[^A-Za-z0-9_-]", "", session_id)
    chunk_path = day_dir / f"camera{camera_id}_{safe_session_id}_parte{part_number}.webm"
    chunk_path.write_bytes(data)
    return chunk_path
