#!/usr/bin/env python3
"""GPU + VRAM detection for a Linux candidate PC. Prefers nvidia-smi
(NVIDIA); falls back to lspci for a name-only read on anything else — no
reliable cross-vendor VRAM query without vendor-specific tooling installed.
"""
import json
import shutil
import socket
import subprocess


def _nvidia_gpus() -> list[dict] | None:
    if not shutil.which("nvidia-smi"):
        return None
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not out:
        return None
    gpus = []
    for line in out.splitlines():
        name, vram_mb, driver = [p.strip() for p in line.split(",")]
        gpus.append({
            "vendor": "NVIDIA", "name": name,
            "vram_mb": int(vram_mb), "driver_version": driver,
        })
    return gpus


def _lspci_gpus() -> list[dict]:
    if not shutil.which("lspci"):
        return []
    out = subprocess.run(["lspci"], capture_output=True, text=True).stdout
    return [
        {"vendor": "unknown", "name": line.split(": ", 1)[1], "vram_mb": None, "driver_version": None}
        for line in out.splitlines()
        if "VGA" in line or "3D controller" in line
    ]


def main() -> None:
    gpus = _nvidia_gpus() or _lspci_gpus()
    print(json.dumps({"hostname": socket.gethostname(), "gpus": gpus}, indent=2))


if __name__ == "__main__":
    main()
