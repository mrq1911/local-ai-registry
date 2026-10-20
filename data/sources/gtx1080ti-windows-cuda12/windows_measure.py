"""Windows supporting measurements for the GTX 1080 Ti recipe.

Uses Windows memory counters and read-only nvidia-smi queries. GPU memory is
the total for the desktop, not a claim about this model's allocation alone.
No clock, power, fan, process-control, network, or credential operations.
"""
import argparse
import csv
import ctypes
from ctypes import wintypes
import datetime
import json
import platform
from pathlib import Path
import shutil
import subprocess
import time


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in (
            "total_phys", "avail_phys", "total_page", "avail_page",
            "total_virtual", "avail_virtual", "avail_extended_virtual")]


def memory():
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError()
    return {"physical_total_bytes": status.total_phys,
            "physical_available_bytes": status.avail_phys,
            "memory_load_percent": status.load}


def gpu():
    fields = "name,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw,driver_version"
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=" + fields, "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True, timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW)
    rows = list(csv.reader(result.stdout.splitlines()))
    if len(rows) != 1:
        raise RuntimeError("Expected exactly one GPU; do not choose another card silently")
    values = [value.strip() for value in rows[0]]
    return {"name": values[0], "memory_total_mib": float(values[1]),
            "memory_used_mib": float(values[2]), "utilization_percent": float(values[3]),
            "temperature_c": float(values[4]), "power_w": float(values[5]),
            "driver": values[6]}


def probe(models_dir):
    disk = shutil.disk_usage(models_dir)
    return {"schema": "gtx218/windows-supporting-probe/v1",
            "at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "os": platform.platform(), "architecture": platform.machine(),
            "memory": memory(), "gpu": gpu(),
            "models_disk": {"total_bytes": disk.total, "free_bytes": disk.free},
            "limitations": ["Windows desktop GPU clients remain running",
                            "GPU memory is whole-device usage under WDDM",
                            "No Linux swap, NVMe bandwidth, or reference-panel result is inferred",
                            "This supporting probe does not replace the recipe-kit submission"]}


def watch(path, stop_file, seconds, interval):
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + seconds
    fields = ["time_utc", "mem_available_gb", "swap_used_gb", "gpu_used_mib",
              "gpu_util_percent", "gpu_power_w", "gpu_temperature_c"]
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        while time.monotonic() < deadline and not stop_file.exists():
            mem, card = memory(), gpu()
            writer.writerow({"time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                             "mem_available_gb": round(mem["physical_available_bytes"] / 1e9, 5),
                             "swap_used_gb": "", "gpu_used_mib": card["memory_used_mib"],
                             "gpu_util_percent": card["utilization_percent"],
                             "gpu_power_w": card["power_w"],
                             "gpu_temperature_c": card["temperature_c"]})
            handle.flush()
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("probe")
    p.add_argument("--models-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    w = commands.add_parser("watch")
    w.add_argument("--out", type=Path, required=True)
    w.add_argument("--stop-file", type=Path, required=True)
    w.add_argument("--seconds", type=int, default=3600, choices=range(1, 7201))
    w.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    if args.command == "probe":
        data = probe(args.models_dir)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as out:
            json.dump(data, out, indent=2)
        print(json.dumps(data, indent=2))
    else:
        if not 0.5 <= args.interval <= 60:
            raise SystemExit("interval must be 0.5 to 60 seconds")
        watch(args.out, args.stop_file, args.seconds, args.interval)


if __name__ == "__main__":
    main()
