import csv
import shutil
from pathlib import Path

_INT_FIELDS = ("ram_used_mb", "ram_total_mb", "arm_clock_mhz", "core_clock_mhz")
_FLOAT_FIELDS = ("cpu_pct", "temp_c")
_BOOL_FIELDS = ("undervoltage_now", "freq_capped_now", "throttled_now", "undervoltage_ever")


def read_latest_status(csv_path: Path) -> dict:
    if not csv_path.exists():
        raise FileNotFoundError(f"monitor csv not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise ValueError(f"monitor csv has no data rows: {csv_path}")

    row = rows[-1]
    status = {"timestamp": row["timestamp"]}
    for field in _INT_FIELDS:
        status[field] = int(row[field])
    for field in _FLOAT_FIELDS:
        status[field] = float(row[field])
    for field in _BOOL_FIELDS:
        status[field] = row[field] == "1"
    return status


def get_disk_usage(path: Path) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    mb = 1024 * 1024
    return {
        "disk_used_mb": usage.used // mb,
        "disk_total_mb": usage.total // mb,
    }
