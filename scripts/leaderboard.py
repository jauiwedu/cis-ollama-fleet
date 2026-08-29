#!/usr/bin/env python3
"""Print a combined table across every results/*.json committed so far.

A model "passes" the refusal check for a given prompt if it produced a
non-empty response without erroring — this script doesn't grade whether the
answer is *good*, it just flags outright refusals/errors for a human to
weigh alongside tokens/sec. Read the actual response text in the result
file before picking a winner; this table is a starting point, not a verdict.
"""
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

_REFUSAL_MARKERS = (
    "i cannot", "i can't", "i won't", "i'm not able to", "i am not able to",
    "as an ai", "i'm sorry, but", "i am sorry, but",
)


def _looks_refused(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


def main() -> None:
    files = sorted(RESULTS_DIR.glob("*.json"))
    if not files:
        print("no results yet — run benchmark/run_benchmark.py on a candidate PC first")
        return

    rows = []
    for f in files:
        data = json.loads(f.read_text())
        for run in data["runs"]:
            cap = run.get("capability", {})
            ref = run.get("refusal_check", {})
            tok_rates = [v["tokens_per_sec"] for v in {**cap, **ref}.values()
                         if isinstance(v, dict) and v.get("tokens_per_sec")]
            avg_tps = sum(tok_rates) / len(tok_rates) if tok_rates else None
            refusals = sum(
                1 for v in ref.values()
                if isinstance(v, dict) and "response" in v and _looks_refused(v["response"])
            )
            rows.append({
                "hostname": data["hostname"],
                "tag": run["tag"],
                "avg_tokens_per_sec": round(avg_tps, 1) if avg_tps else None,
                "refusals": f"{refusals}/{len(ref)}",
            })

    width = max(len(r["tag"]) for r in rows) + 2
    print(f"{'host':<16}{'model':<{width}}{'avg tok/s':<12}{'refusals'}")
    print("-" * (16 + width + 12 + 10))
    for r in sorted(rows, key=lambda r: (r["avg_tokens_per_sec"] or 0), reverse=True):
        tps = r["avg_tokens_per_sec"] if r["avg_tokens_per_sec"] is not None else "n/a"
        print(f"{r['hostname']:<16}{r['tag']:<{width}}{str(tps):<12}{r['refusals']}")


if __name__ == "__main__":
    main()
