#!/usr/bin/env python3
"""Regenerate litellm_config.yaml's model_list from benchmark results.

For every results/<hostname>.json, picks each model's route (coding/text/
etc. — see models/candidates.json's "role" field) and keeps the fastest
non-refusing tag per host per route, per scripts/leaderboard.py's own
refusal heuristic. Prints YAML to stdout — review it before pasting over
the model_list block in litellm_config.yaml; this does not write the file
for you, so a bad benchmark run can't silently reconfigure the live proxy.

Usage:
    python orchestrator/generate_config.py > /tmp/model_list.yaml
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"
CANDIDATES_FILE = REPO_ROOT / "models" / "candidates.json"

_REFUSAL_MARKERS = (
    "i cannot", "i can't", "i won't", "i'm not able to", "i am not able to",
    "as an ai", "i'm sorry, but", "i am sorry, but",
)


def _looks_refused(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


def _host_base_url(hostname: str) -> str:
    # cis.lab is the confirmed-resolving domain for lab PCs (verified via DNS
    # lookup against G014-10) — lab.uiw.edu never resolved and was a guess.
    return f"http://{hostname}.cis.lab:11434"


def main() -> None:
    candidates = {c["ollama_tag"]: c for c in json.loads(CANDIDATES_FILE.read_text())}
    files = sorted(RESULTS_DIR.glob("*.json"))
    if not files:
        print("# no results yet — run benchmark/run_benchmark.py on a candidate PC first")
        return

    print("model_list:")
    for f in files:
        data = json.loads(f.read_text())
        hostname = data["hostname"]
        base_url = _host_base_url(hostname)

        # score = avg tokens/sec across all prompts, disqualified if any
        # refusal_check prompt looks refused
        scored = []
        for run in data["runs"]:
            cap, ref = run.get("capability", {}), run.get("refusal_check", {})
            all_vals = {**cap, **ref}
            rates = [v["tokens_per_sec"] for v in all_vals.values()
                     if isinstance(v, dict) and v.get("tokens_per_sec")]
            if not rates:
                continue
            refused = any(
                isinstance(v, dict) and "response" in v and _looks_refused(v["response"])
                for v in ref.values()
            )
            if refused:
                continue
            scored.append((sum(rates) / len(rates), run["tag"]))

        if not scored:
            print(f"  # {hostname}: no candidate passed the refusal check — skipped")
            continue

        scored.sort(reverse=True)
        best_tag = scored[0][1]
        role = candidates.get(best_tag, {}).get("family", "general")

        print(f"  - model_name: {role}-agent")
        print(f"    litellm_params:")
        print(f"      model: ollama/{best_tag}")
        print(f"      api_base: {base_url}")
        print(f"    model_info:")
        print(f"      host: {hostname}")
        print(f"      role: {role}")


if __name__ == "__main__":
    main()
