from pathlib import Path

import pytest

from server.monitor_status import get_disk_usage, read_latest_status

CSV_HEADER = "timestamp,cpu_pct,ram_used_mb,ram_total_mb,temp_c,arm_clock_mhz,core_clock_mhz,undervoltage_now,freq_capped_now,throttled_now,undervoltage_ever\n"


def test_read_latest_status_parses_last_row(tmp_path: Path):
    csv_path = tmp_path / "monitor.csv"
    csv_path.write_text(
        CSV_HEADER
        + "2026-08-20 18:00:00,5.0,150,955,40.0,700,275,0,0,0,0\n"
        + "2026-08-20 18:00:02,8.2,164,955,41.3,700,275,0,0,0,0\n"
    )

    status = read_latest_status(csv_path)

    assert status == {
        "timestamp": "2026-08-20 18:00:02",
        "cpu_pct": 8.2,
        "ram_used_mb": 164,
        "ram_total_mb": 955,
        "temp_c": 41.3,
        "arm_clock_mhz": 700,
        "core_clock_mhz": 275,
        "undervoltage_now": False,
        "freq_capped_now": False,
        "throttled_now": False,
        "undervoltage_ever": False,
    }


def test_read_latest_status_flags_true_when_set(tmp_path: Path):
    csv_path = tmp_path / "monitor.csv"
    csv_path.write_text(
        CSV_HEADER + "2026-08-20 18:00:00,5.0,150,955,40.0,700,275,1,1,1,1\n"
    )

    status = read_latest_status(csv_path)

    assert status["undervoltage_now"] is True
    assert status["freq_capped_now"] is True
    assert status["throttled_now"] is True
    assert status["undervoltage_ever"] is True


def test_read_latest_status_raises_when_file_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        read_latest_status(tmp_path / "does-not-exist.csv")


def test_read_latest_status_raises_when_only_header(tmp_path: Path):
    csv_path = tmp_path / "monitor.csv"
    csv_path.write_text(CSV_HEADER)

    with pytest.raises(ValueError):
        read_latest_status(csv_path)


def test_read_latest_status_skips_null_padded_row_from_unclean_shutdown(tmp_path: Path):
    csv_path = tmp_path / "monitor.csv"
    good_row = "2026-08-20 18:00:00,5.0,150,955,40.0,700,275,0,0,0,0\n"
    corrupted_row = "\x00" * 200 + "2026-08-21 09:01:39,30.8,157,955,44.0,1200,400,0,0,0,0\n"
    csv_path.write_text(CSV_HEADER + good_row + corrupted_row)

    status = read_latest_status(csv_path)

    assert status["timestamp"] == "2026-08-21 09:01:39"
    assert status["cpu_pct"] == 30.8


def test_read_latest_status_falls_back_when_last_row_unparseable(tmp_path: Path):
    csv_path = tmp_path / "monitor.csv"
    good_row = "2026-08-20 18:00:00,5.0,150,955,40.0,700,275,0,0,0,0\n"
    truncated_row = "2026-08-20 18:00:02,8.2,164,955\n"
    csv_path.write_text(CSV_HEADER + good_row + truncated_row)

    status = read_latest_status(csv_path)

    assert status["timestamp"] == "2026-08-20 18:00:00"


def test_get_disk_usage_returns_plausible_totals(tmp_path: Path):
    usage = get_disk_usage(tmp_path)

    assert usage["disk_total_mb"] > 0
    assert 0 <= usage["disk_used_mb"] <= usage["disk_total_mb"]


def test_get_disk_usage_creates_missing_directory(tmp_path: Path):
    target = tmp_path / "does" / "not" / "exist"

    usage = get_disk_usage(target)

    assert target.is_dir()
    assert usage["disk_total_mb"] > 0
