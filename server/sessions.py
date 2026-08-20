def start_session(registry: dict, camera_id: int, name: str, quality: str, now: float) -> None:
    registry[camera_id] = {
        "name": name,
        "quality": quality,
        "started_at": now,
        "chunks_received": 0,
        "bytes_received": 0,
        "last_chunk_at": None,
    }


def stop_session(registry: dict, camera_id: int) -> None:
    registry.pop(camera_id, None)


def record_chunk(registry: dict, camera_id: int, size_bytes: int, now: float) -> None:
    session = registry.get(camera_id)
    if session is None:
        return
    session["chunks_received"] += 1
    session["bytes_received"] += size_bytes
    session["last_chunk_at"] = now


def list_sessions(registry: dict, now: float) -> list[dict]:
    result = []
    for camera_id, session in registry.items():
        last_chunk_at = session["last_chunk_at"]
        result.append({
            "camera": camera_id,
            "name": session["name"],
            "quality": session["quality"],
            "elapsed_seconds": int(now - session["started_at"]),
            "chunks_received": session["chunks_received"],
            "bytes_received": session["bytes_received"],
            "seconds_since_last_chunk": None if last_chunk_at is None else int(now - last_chunk_at),
        })
    return result
