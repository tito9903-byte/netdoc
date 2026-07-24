from __future__ import annotations

import os
import platform
from pathlib import Path
import shutil
import socket
import sys
from typing import Any


def _percent(used: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((used / total) * 100, 1)


def _format_bytes(value: int | float) -> str:
    amount = float(max(value, 0))
    units = ("B", "KB", "MB", "GB", "TB", "PB")

    for unit in units:
        if amount < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024

    return f"{amount:.1f} PB"


def _read_meminfo(path: Path = Path("/proc/meminfo")) -> dict[str, int]:
    values: dict[str, int] = {}

    try:
        for line in path.read_text().splitlines():
            key, _, raw_value = line.partition(":")
            parts = raw_value.strip().split()
            if not parts:
                continue
            value = int(parts[0])
            if len(parts) > 1 and parts[1].lower() == "kb":
                value *= 1024
            values[key] = value
    except (OSError, ValueError):
        return {}

    return values


def _read_uptime(path: Path = Path("/proc/uptime")) -> float:
    try:
        return float(path.read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return 0.0


def _read_network_totals(
    path: Path = Path("/proc/net/dev"),
) -> tuple[int, int]:
    received = 0
    transmitted = 0

    try:
        lines = path.read_text().splitlines()[2:]
    except OSError:
        return received, transmitted

    for line in lines:
        if ":" not in line:
            continue
        name, values = line.split(":", 1)
        if name.strip() == "lo":
            continue
        fields = values.split()
        if len(fields) < 16:
            continue
        try:
            received += int(fields[0])
            transmitted += int(fields[8])
        except ValueError:
            continue

    return received, transmitted


def _format_uptime(seconds: float) -> str:
    total = max(int(seconds), 0)
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days} d")
    if hours or days:
        parts.append(f"{hours} h")
    parts.append(f"{minutes} min")
    return " ".join(parts)


def _severity(percent: float) -> str:
    if percent >= 90:
        return "critical"
    if percent >= 75:
        return "warning"
    return "healthy"


def collect_system_health(
    *,
    disk_path: str = "/",
) -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1

    try:
        load_1, load_5, load_15 = os.getloadavg()
    except (AttributeError, OSError):
        load_1 = load_5 = load_15 = 0.0

    load_1 = max(load_1, 0.0)
    load_5 = max(load_5, 0.0)
    load_15 = max(load_15, 0.0)
    load_percent = round((load_1 / cpu_count) * 100, 1)
    memory = _read_meminfo()
    memory_total = int(memory.get("MemTotal", 0))
    memory_available = int(memory.get("MemAvailable", 0))
    memory_used = max(memory_total - memory_available, 0)
    memory_percent = _percent(memory_used, memory_total)

    try:
        disk = shutil.disk_usage(disk_path)
        disk_total = int(disk.total)
        disk_used = int(disk.used)
        disk_free = int(disk.free)
    except OSError:
        disk_total = disk_used = disk_free = 0

    disk_percent = _percent(disk_used, disk_total)
    rx_bytes, tx_bytes = _read_network_totals()
    uptime_seconds = _read_uptime()

    return {
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "process_id": os.getpid(),
            "executable": sys.executable,
            "uptime_seconds": uptime_seconds,
            "uptime_label": _format_uptime(uptime_seconds),
        },
        "cpu": {
            "logical_count": cpu_count,
            "load_1": round(load_1, 2),
            "load_5": round(load_5, 2),
            "load_15": round(load_15, 2),
            "load_percent": load_percent,
            "severity": _severity(load_percent),
        },
        "memory": {
            "total": memory_total,
            "used": memory_used,
            "available": memory_available,
            "total_label": _format_bytes(memory_total),
            "used_label": _format_bytes(memory_used),
            "available_label": _format_bytes(memory_available),
            "percent": memory_percent,
            "severity": _severity(memory_percent),
        },
        "disk": {
            "path": disk_path,
            "total": disk_total,
            "used": disk_used,
            "free": disk_free,
            "total_label": _format_bytes(disk_total),
            "used_label": _format_bytes(disk_used),
            "free_label": _format_bytes(disk_free),
            "percent": disk_percent,
            "severity": _severity(disk_percent),
        },
        "network": {
            "received": rx_bytes,
            "transmitted": tx_bytes,
            "received_label": _format_bytes(rx_bytes),
            "transmitted_label": _format_bytes(tx_bytes),
        },
    }
