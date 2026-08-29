# CIS Ollama Fleet

Prep work for the CIS lab's local Ollama fleet (`hydra-llm-cluster`), feeding
into the AI Fleet dashboard already built in
[ciscsec-command-center](https://github.com/jauiwedu/ciscsec-command-center).

This repo answers one question per candidate PC: **given this machine's GPU,
which open-weight model should it run for security-research work** (CTF
assistance, red-team/pentest note-taking, malware/log triage) — where a model
that reflexively refuses security-flavored prompts is a worse fit than one
that doesn't, and where the model has to actually fit in VRAM at a usable
quant.

## Process

1. **Inventory candidate PCs.** Pick one as the benchmark reference PC —
   whichever is representative of the group (or the one most people will
   actually be sitting at).
2. **Detect its GPU + VRAM** — [`benchmark/Get-GpuInfo.ps1`](benchmark/Get-GpuInfo.ps1)
   (Windows lab machines) or [`benchmark/gpu_info.sh`](benchmark/gpu_info.sh)
   (Linux, if any candidate runs it).
3. **Run the benchmark** — [`benchmark/run_benchmark.py`](benchmark/run_benchmark.py)
   pulls each candidate model that plausibly fits the detected VRAM, runs the
   fixed prompt set in [`benchmark/prompts.json`](benchmark/prompts.json)
   against Ollama's local API, and records tokens/sec, load time, and
   peak VRAM into `results/<hostname>.json`.
4. **Compare** — commit each PC's result file; `scripts/leaderboard.py` prints
   a combined table across every PC that's run the benchmark so far.
5. **Pick per-PC defaults** — the model that's fastest *and* doesn't refuse
   the security-flavored prompts in the set wins for that PC's tier. Record
   the pick in that PC's result file (`"selected": "<ollama-tag>"`) and set it
   as the default model the fleet dashboard shows for that node.

## Model shortlist

[`models/candidates.md`](models/candidates.md) is the curated list of
open-weight models worth benchmarking, grouped by VRAM tier, with the
`ollama pull` tag for each. It's deliberately narrow — models chosen because
they're known to have a light refusal posture out of the box, not because
they're the most capable model at that size. Capability still matters, which
is exactly what the benchmark's refusal-check prompts are for: a model that's
fast and permissive but useless at the actual task doesn't get picked either.

## Why this matters here specifically

This fleet serves the CIS/CSEC security lab — see
[ciscsec-command-center](https://github.com/jauiwedu/ciscsec-command-center)'s
docs for the full picture. The assistant these models power is **propose-only**
(see `backend/app/clients/assistant.py` in that repo) — it never has a path to
execute a privileged action on its own, regardless of which model answers.
Picking a less-refusal-prone model changes what it's willing to *discuss*
(exploit mechanics, malware behavior, log analysis for an ongoing incident),
not what it's able to *do*.

## Repo layout

```
benchmark/
  Get-GpuInfo.ps1      GPU + VRAM detection, Windows
  gpu_info.sh           GPU + VRAM detection, Linux
  prompts.json          fixed benchmark prompt set (capability + refusal checks)
  run_benchmark.py      drives Ollama's local API, writes results/<hostname>.json
models/
  candidates.md         curated model shortlist by VRAM tier
  candidates.json        same data, machine-readable (used by scripts/recommend.py)
results/
  <hostname>.json        one file per benchmarked PC (committed, so they're comparable)
scripts/
  recommend.py           `python recommend.py --vram-gb 12` -> which candidates fit
  leaderboard.py          prints a combined table across every results/*.json
```
