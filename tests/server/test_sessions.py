from server.sessions import list_sessions, record_chunk, start_session, stop_session


def test_start_session_creates_entry():
    registry = {}
    start_session(registry, camera_id=1, name="Carlos", quality="hd30", now=1000.0)

    assert registry[1]["name"] == "Carlos"
    assert registry[1]["quality"] == "hd30"
    assert registry[1]["started_at"] == 1000.0
    assert registry[1]["chunks_received"] == 0
    assert registry[1]["bytes_received"] == 0
    assert registry[1]["last_chunk_at"] is None


def test_start_session_replaces_existing_entry_for_same_camera():
    registry = {}
    start_session(registry, camera_id=1, name="Carlos", quality="hd30", now=1000.0)
    start_session(registry, camera_id=1, name="Ana", quality="fhd60", now=2000.0)

    assert registry[1]["name"] == "Ana"
    assert registry[1]["quality"] == "fhd60"
    assert registry[1]["started_at"] == 2000.0


def test_stop_session_removes_entry():
    registry = {}
    start_session(registry, camera_id=1, name="Carlos", quality="hd30", now=1000.0)

    stop_session(registry, camera_id=1)

    assert 1 not in registry


def test_stop_session_on_missing_camera_does_not_raise():
    registry = {}

    stop_session(registry, camera_id=1)

    assert registry == {}


def test_record_chunk_updates_counters_and_last_chunk_time():
    registry = {}
    start_session(registry, camera_id=1, name="Carlos", quality="hd30", now=1000.0)

    record_chunk(registry, camera_id=1, size_bytes=500, now=1005.0)
    record_chunk(registry, camera_id=1, size_bytes=300, now=1010.0)

    assert registry[1]["chunks_received"] == 2
    assert registry[1]["bytes_received"] == 800
    assert registry[1]["last_chunk_at"] == 1010.0


def test_record_chunk_for_camera_without_session_is_ignored():
    registry = {}

    record_chunk(registry, camera_id=1, size_bytes=500, now=1005.0)

    assert registry == {}


def test_list_sessions_returns_computed_fields():
    registry = {}
    start_session(registry, camera_id=1, name="Carlos", quality="hd30", now=1000.0)
    record_chunk(registry, camera_id=1, size_bytes=500, now=1020.0)

    result = list_sessions(registry, now=1030.0)

    assert result == [
        {
            "camera": 1,
            "name": "Carlos",
            "quality": "hd30",
            "elapsed_seconds": 30,
            "chunks_received": 1,
            "bytes_received": 500,
            "seconds_since_last_chunk": 10,
        }
    ]


def test_list_sessions_reports_none_when_no_chunk_received_yet():
    registry = {}
    start_session(registry, camera_id=1, name="Carlos", quality="hd30", now=1000.0)

    result = list_sessions(registry, now=1005.0)

    assert result[0]["seconds_since_last_chunk"] is None


def test_list_sessions_empty_registry_returns_empty_list():
    assert list_sessions({}, now=1000.0) == []
