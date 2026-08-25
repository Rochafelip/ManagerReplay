from pathlib import Path

from server.events import list_events, record_event, remove_event


def test_record_event_creates_first_lance_with_padded_number(tmp_path: Path):
    events_file = tmp_path / "events.jsonl"

    event = record_event(events_file, camera_id="1")

    assert event["nome"] == "Lance Epico 001"
    assert event["camera"] == "1"
    assert event["timestamp"].endswith("Z")


def test_record_event_increments_across_calls(tmp_path: Path):
    events_file = tmp_path / "events.jsonl"

    record_event(events_file, camera_id="1")
    second = record_event(events_file, camera_id="2")

    assert second["nome"] == "Lance Epico 002"


def test_list_events_returns_empty_when_file_missing(tmp_path: Path):
    events_file = tmp_path / "events.jsonl"

    assert list_events(events_file) == []


def test_list_events_returns_recorded_events_in_order(tmp_path: Path):
    events_file = tmp_path / "events.jsonl"
    record_event(events_file, camera_id="1")
    record_event(events_file, camera_id="1")

    events = list_events(events_file)

    assert [e["nome"] for e in events] == ["Lance Epico 001", "Lance Epico 002"]


def test_remove_event_deletes_matching_event_and_returns_it(tmp_path: Path):
    events_file = tmp_path / "events.jsonl"
    record_event(events_file, camera_id="1")
    second = record_event(events_file, camera_id="2")

    removed = remove_event(events_file, "Lance Epico 001")

    assert removed["nome"] == "Lance Epico 001"
    remaining = list_events(events_file)
    assert [e["nome"] for e in remaining] == ["Lance Epico 002"]
    assert remaining[0] == second


def test_remove_event_returns_none_when_name_not_found(tmp_path: Path):
    events_file = tmp_path / "events.jsonl"
    record_event(events_file, camera_id="1")

    removed = remove_event(events_file, "Lance Epico 999")

    assert removed is None
    assert len(list_events(events_file)) == 1
