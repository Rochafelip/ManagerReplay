import re
from pathlib import Path

# Matches one uploaded recording chunk, e.g. "camera2_2026-08-20T18-32-10_parte3.webm".
# Individual parts (besides part 1) aren't playable on their own — see
# storage.find_session_parts — so the listing groups them into one entry
# per (camera, session) recording instead of showing every part.
_CHUNK_PART_PATTERN = re.compile(r"^camera(\d+)_(.+)_parte(\d+)\.webm$")


def _group_recording_parts(entries: list[dict]) -> list[dict]:
    grouped = {}
    passthrough = []

    for entry in entries:
        match = None if entry["is_dir"] else _CHUNK_PART_PATTERN.match(entry["name"])
        if not match:
            passthrough.append(entry)
            continue

        camera_id, session_id = match.group(1), match.group(2)
        group = grouped.setdefault((camera_id, session_id), {"size": 0, "mtime": 0.0})
        group["size"] += entry["size"]
        group["mtime"] = max(group["mtime"], entry["mtime"])

    merged = [
        {
            "name": f"camera{camera_id}_{session_id}.webm",
            "is_dir": False,
            "size": group["size"],
            "mtime": group["mtime"],
        }
        for (camera_id, session_id), group in grouped.items()
    ]

    return sorted(passthrough + merged, key=lambda e: (not e["is_dir"], e["name"]))


def list_directory(storage_root: Path, rel_path: str) -> list[dict]:
    storage_root = storage_root.resolve()
    target = (storage_root / rel_path).resolve()

    if storage_root != target and storage_root not in target.parents:
        raise ValueError(f"path escapes storage root: {rel_path}")

    if not target.is_dir():
        raise FileNotFoundError(f"not a directory: {rel_path}")

    entries = []
    for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name)):
        stat = item.stat()
        entries.append({
            "name": item.name,
            "is_dir": item.is_dir(),
            "size": None if item.is_dir() else stat.st_size,
            "mtime": stat.st_mtime,
        })
    return _group_recording_parts(entries)
