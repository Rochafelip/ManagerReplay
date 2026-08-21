import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def parse_cpu_pct(cpu_line: str) -> float:
    match = re.search(r"([\d.]+)\s*%?\s*id", cpu_line)
    if not match:
        raise ValueError(f"could not parse CPU idle from: {cpu_line!r}")
    idle = float(match.group(1))
    return round(100 - idle, 1)


def parse_ram(free_output: str) -> tuple[int, int]:
    mem_line = next(line for line in free_output.splitlines() if line.startswith("Mem:"))
    parts = mem_line.split()
    total, used = int(parts[1]), int(parts[2])
    return used, total


def parse_temp(vcgencmd_output: str) -> float:
    match = re.search(r"[\d.]+", vcgencmd_output)
    if not match:
        raise ValueError(f"could not parse temperature from: {vcgencmd_output!r}")
    return float(match.group())


def parse_clock_mhz(vcgencmd_output: str) -> int:
    hz = int(vcgencmd_output.strip().split("=")[1])
    return hz // 1_000_000


def parse_throttled_flags(vcgencmd_output: str) -> dict:
    value = int(vcgencmd_output.strip().split("=")[1], 16)
    return {
        "undervoltage_now": bool(value & (1 << 0)),
        "freq_capped_now": bool(value & (1 << 1)),
        "throttled_now": bool(value & (1 << 2)),
        "undervoltage_ever": bool(value & (1 << 16)),
    }


def _run(cmd: list) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def read_live_status() -> dict:
    top_output = _run(["top", "-bn1"])
    cpu_line = next(line for line in top_output.splitlines() if "Cpu(s)" in line)
    ram_used, ram_total = parse_ram(_run(["free", "-m"]))

    status = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cpu_pct": parse_cpu_pct(cpu_line),
        "ram_used_mb": ram_used,
        "ram_total_mb": ram_total,
        "temp_c": parse_temp(_run(["vcgencmd", "measure_temp"])),
        "arm_clock_mhz": parse_clock_mhz(_run(["vcgencmd", "measure_clock", "arm"])),
        "core_clock_mhz": parse_clock_mhz(_run(["vcgencmd", "measure_clock", "core"])),
    }
    status.update(parse_throttled_flags(_run(["vcgencmd", "get_throttled"])))
    return status


def get_disk_usage(path: Path) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    mb = 1024 * 1024
    return {
        "disk_used_mb": usage.used // mb,
        "disk_total_mb": usage.total // mb,
    }
