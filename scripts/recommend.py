#!/usr/bin/env python3
"""Which candidate models plausibly fit a given VRAM budget.

Usage: python scripts/recommend.py --vram-gb 12
"""
import argparse
import json
from pathlib import Path

CANDIDATES_FILE = Path(__file__).resolve().parent.parent / "models" / "candidates.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vram-gb", type=float, required=True)
    args = ap.parse_args()

    candidates = json.loads(CANDIDATES_FILE.read_text())
    fits = [c for c in candidates if c["vram_gb_min"] <= args.vram_gb]
    fits.sort(key=lambda c: c["params_b"], reverse=True)

    if not fits:
        print(f"nothing in models/candidates.json fits {args.vram_gb}GB — the smallest option needs "
              f"{min(c['vram_gb_min'] for c in candidates)}GB")
        return

    print(f"candidates that plausibly fit {args.vram_gb}GB VRAM (largest first):\n")
    for c in fits:
        print(f"  {c['ollama_tag']:<32} {c['params_b']:>4}B params, needs ~{c['vram_gb_min']}GB")
        print(f"    {c['notes']}\n")


if __name__ == "__main__":
    main()
