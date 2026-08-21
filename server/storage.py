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


def find_session_parts(day_dir: Path, camera_id: str, session_id: str) -> list[Path]:
    """Finds every uploaded chunk of one recording, in playback order.

    Chunks are Matroska continuation clusters (only part 1 has a standalone
    WebM header), so they must be concatenated in this order to produce a
    playable file — see chunks_receiver._serve_merged_recording.
    """
    pattern = re.compile(rf"^camera{re.escape(str(camera_id))}_{re.escape(session_id)}_parte(\d+)\.webm$")
    numbered = []
    for item in day_dir.iterdir():
        if not item.is_file():
            continue
        match = pattern.match(item.name)
        if match:
            numbered.append((int(match.group(1)), item))
    numbered.sort(key=lambda pair: pair[0])
    return [item for _, item in numbered]
