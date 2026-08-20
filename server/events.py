import json
from datetime import datetime, timezone
from pathlib import Path


def _next_name(events_file: Path) -> str:
    count = 0
    if events_file.exists():
        with events_file.open("r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip())
    return f"LanceEpico {count + 1:03d}"


def record_event(events_file: Path, camera_id: str) -> dict:
    events_file.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "nome": _next_name(events_file),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "camera": camera_id,
    }
    with events_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def list_events(events_file: Path) -> list[dict]:
    if not events_file.exists():
        return []
    with events_file.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
