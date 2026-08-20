from pathlib import Path

import pytest

from server.monitor_status import read_latest_status

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
