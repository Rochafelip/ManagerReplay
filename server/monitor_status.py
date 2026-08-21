import csv
import shutil
from pathlib import Path

_INT_FIELDS = ("ram_used_mb", "ram_total_mb", "arm_clock_mhz", "core_clock_mhz")
_FLOAT_FIELDS = ("cpu_pct", "temp_c")
_BOOL_FIELDS = ("undervoltage_now", "freq_capped_now", "throttled_now", "undervoltage_ever")
_ALL_FIELDS = ("timestamp",) + _INT_FIELDS + _FLOAT_FIELDS + _BOOL_FIELDS


def _parse_row(row: dict) -> dict:
    status = {"timestamp": row["timestamp"]}
    for field in _INT_FIELDS:
        status[field] = int(row[field])
    for field in _FLOAT_FIELDS:
        status[field] = float(row[field])
    for field in _BOOL_FIELDS:
        status[field] = row[field] == "1"
    return status


def read_latest_status(csv_path: Path) -> dict:
    if not csv_path.exists():
        raise FileNotFoundError(f"monitor csv not found: {csv_path}")

    # An unclean shutdown (e.g. SD card power-cut mid-write) can leave NUL
    # bytes padded into the last row(s) of the CSV -- strip them and skip
    # any row that still doesn't parse cleanly, walking back from the end.
    text = csv_path.read_text(encoding="utf-8", errors="replace").replace("\x00", "")
    rows = list(csv.DictReader(text.splitlines()))

    if not rows:
        raise ValueError(f"monitor csv has no data rows: {csv_path}")

    for row in reversed(rows):
        if any(row.get(field) in (None, "") for field in _ALL_FIELDS):
            continue
        try:
            return _parse_row(row)
        except ValueError:
            continue

    raise ValueError(f"monitor csv has no valid data rows: {csv_path}")


def get_disk_usage(path: Path) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    mb = 1024 * 1024
    return {
        "disk_used_mb": usage.used // mb,
        "disk_total_mb": usage.total // mb,
    }
