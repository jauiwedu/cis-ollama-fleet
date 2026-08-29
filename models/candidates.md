# Model shortlist

Machine-readable version: [`candidates.json`](candidates.json) (used by
`scripts/recommend.py` and `scripts/leaderboard.py`).

**Verify tags before pulling.** Ollama's library changes over time — run
`ollama search <family>` or check `ollama.com/library/<family>` against the
tag below before benchmarking, in case the exact tag has moved.

`vram_gb_min` is a rough floor for a Q4_K_M-class quant at a modest context
window (~4K tokens) — treat it as "worth trying," not a guarantee. The
benchmark script records actual VRAM use per machine so this gets corrected
by real data as PCs get benchmarked.

| Tier | Tag | Params | Min VRAM | Why it's here |
|---|---|---|---|---|
| small | `llama2-uncensored:7b` | 7B | 6GB | cheap fallback, benchmark before trusting |
| small | `wizard-vicuna-uncensored:7b` | 7B | 6GB | consistently light refusals, good baseline |
| small | `dolphin-llama3:8b` | 8B | 6GB | Dolphin fine-tune of Llama 3, strong default 8GB pick |
| small | `dolphin3:8b` | 8B | 6GB | newer Dolphin gen, compare head-to-head with `dolphin-llama3:8b` |
| small | `openhermes:7b` | 7B | 6GB | lighter guardrails + strong general capability |
| medium | `wizard-vicuna-uncensored:13b` | 13B | 10GB | step up if VRAM allows |
| large | `nous-hermes2-mixtral:8x7b` | 47B (MoE, ~13B active) | 26GB | fast for its size (MoE), needs the VRAM for full weights |
| large | `dolphin-mixtral:8x7b` | 47B (MoE, ~13B active) | 26GB | strongest low-refusal pick if hardware supports it |
| xlarge | `dolphin-llama3:70b` | 70B | 40GB | best reasoning here, only for 48GB+ cards |

## Why these and not base Llama/Mistral instruct models

Base instruct-tuned models (`llama3.1`, `mistral`, etc.) are worth
benchmarking too as a capability baseline, but they ship with the vendor's
default safety tuning, which routinely refuses security-research-flavored
prompts (exploit mechanics, malware behavior analysis, "how would an attacker
do X") even when the actual use is defensive. The models above are
fine-tunes specifically built to drop that reflexive refusal layer while
keeping the base model's underlying capability — that's the trade this list
is selecting for.

## Benchmark, don't assume

This list is a starting point, not a ranking. `benchmark/prompts.json`
includes both capability-check prompts and refusal-check prompts — a model
that's fast but gives a useless or refused answer on the refusal-check
prompts shouldn't win its VRAM tier just because it's smaller. Let
`scripts/leaderboard.py` settle it per machine.
