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


def sanitize_lance_name(nome: str) -> str:
    """Strips a lance's display name down to filename-safe characters.

    Mirrored in lances.html's JS so a clip's filename can be derived
    identically on both sides from the event's "nome" field alone —
    there's no separate "clip path" stored in events.jsonl.
    """
    return re.sub(r"[^A-Za-z0-9]", "", nome)


def save_lance_clip(day_dir: Path, camera_id: str, nome: str, data: bytes) -> Path:
    lances_dir = day_dir / "lances"
    lances_dir.mkdir(parents=True, exist_ok=True)
    clip_path = lances_dir / f"lance_camera{camera_id}_{sanitize_lance_name(nome)}.webm"
    clip_path.write_bytes(data)
    return clip_path
