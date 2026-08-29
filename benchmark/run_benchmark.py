#!/usr/bin/env python3
"""Benchmark a set of Ollama models on this machine and write
results/<hostname>.json.

Usage:
    python run_benchmark.py --models dolphin-llama3:8b dolphin3:8b
    python run_benchmark.py --all-in-tier 8   # every candidate with vram_gb_min <= 8

Requires Ollama running locally (default http://localhost:11434) with the
target models already pulled, or --pull to pull them first.
"""
import argparse
import json
import socket
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_FILE = REPO_ROOT / "models" / "candidates.json"
PROMPTS_FILE = REPO_ROOT / "benchmark" / "prompts.json"
RESULTS_DIR = REPO_ROOT / "results"


def _api(base_url: str, path: str, payload: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def pull_model(base_url: str, tag: str) -> None:
    print(f"  pulling {tag} ...", file=sys.stderr)
    req = urllib.request.Request(
        f"{base_url}/api/pull",
        data=json.dumps({"name": tag, "stream": False}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=1800) as resp:
        resp.read()


def run_prompt(base_url: str, tag: str, prompt: str) -> dict:
    t0 = time.time()
    res = _api(base_url, "/api/generate", {"model": tag, "prompt": prompt, "stream": False})
    wall_seconds = time.time() - t0

    eval_count = res.get("eval_count", 0)
    eval_ns = res.get("eval_duration", 0)
    tokens_per_sec = (eval_count / (eval_ns / 1e9)) if eval_ns else None

    return {
        "wall_seconds": round(wall_seconds, 2),
        "load_duration_ms": round(res.get("load_duration", 0) / 1e6, 1),
        "eval_count": eval_count,
        "tokens_per_sec": round(tokens_per_sec, 1) if tokens_per_sec else None,
        "response": res.get("response", ""),
    }


def benchmark_model(base_url: str, tag: str, prompts: dict) -> dict:
    print(f"benchmarking {tag}", file=sys.stderr)
    out = {"tag": tag, "capability": {}, "refusal_check": {}}
    for group in ("capability", "refusal_check"):
        for item in prompts[group]:
            print(f"  [{group}] {item['id']}", file=sys.stderr)
            try:
                out[group][item["id"]] = run_prompt(base_url, tag, item["prompt"])
            except Exception as exc:  # noqa: BLE001 — record and keep going
                out[group][item["id"]] = {"error": str(exc)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", help="explicit ollama tags to benchmark")
    ap.add_argument("--all-in-tier", type=int, help="benchmark every candidate with vram_gb_min <= this many GB")
    ap.add_argument("--base-url", default="http://localhost:11434")
    ap.add_argument("--pull", action="store_true", help="pull each model before benchmarking it")
    args = ap.parse_args()

    candidates = json.loads(CANDIDATES_FILE.read_text())
    prompts = json.loads(PROMPTS_FILE.read_text())

    if args.models:
        tags = args.models
    elif args.all_in_tier is not None:
        tags = [c["ollama_tag"] for c in candidates if c["vram_gb_min"] <= args.all_in_tier]
    else:
        ap.error("pass --models or --all-in-tier")

    if not tags:
        print("no candidates matched — check models/candidates.json", file=sys.stderr)
        sys.exit(1)

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{socket.gethostname()}.json"

    results = []
    for tag in tags:
        if args.pull:
            try:
                pull_model(args.base_url, tag)
            except Exception as exc:  # noqa: BLE001 — record and keep going
                print(f"  pull failed for {tag}: {exc}", file=sys.stderr)
                results.append({"tag": tag, "error": f"pull failed: {exc}"})
                out_path.write_text(json.dumps({"hostname": socket.gethostname(), "runs": results}, indent=2))
                continue
        results.append(benchmark_model(args.base_url, tag, prompts))
        out_path.write_text(json.dumps({"hostname": socket.gethostname(), "runs": results}, indent=2))

    print(f"wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
