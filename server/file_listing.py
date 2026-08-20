from pathlib import Path


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
    return entries
