# Orchestrator: LiteLLM Proxy in front of the lab's Ollama fleet

One gateway, one URL, per-person API keys. Students, professors, and you all
hit the same endpoint; LiteLLM routes each request to whichever lab PC is
hosting the requested agent (coding / text / vision / etc.), and every key's
usage is tracked and capped separately.

We're not writing this gateway from scratch — [LiteLLM Proxy](https://github.com/BerriAI/litellm)
is an existing, actively maintained open-source project built for exactly
this: many backend models behind one OpenAI- and Anthropic-compatible API,
with virtual per-user keys, budgets, and routing baked in.

## How it fits together

```
student / prof / you
        │  (their own virtual API key)
        ▼
  LiteLLM Proxy  ── reads litellm_config.yaml ──►  coding-agent  → g014-01:11434 (dolphin-llama3:8b)
  (one URL,                                        text-agent    → g014-01:11434 (dolphin3:8b)
   port 4000)                                       vision-agent  → g014-02:11434 (llava:13b)
        │                                            ...more PCs as they're benchmarked
        ▼
  Postgres (keys, budgets, usage — not model weights)
```

Callers never see individual PC hostnames or IPs — they ask for a *route*
(`coding-agent`, `text-agent`, ...) and LiteLLM picks a healthy backend
serving it.

## 1. Deploy the proxy

Needs Docker on whichever machine will host the gateway (a lab server, not
one of the benchmark PCs — it should stay up independent of any one
workstation).

```bash
cd orchestrator
cp .env.example .env
# edit .env: set LITELLM_MASTER_KEY and POSTGRES_PASSWORD to real random values
docker compose up -d
```

The proxy is now listening on `http://<gateway-host>:4000`. `LITELLM_MASTER_KEY`
is the admin key — it can mint/revoke other keys and see fleet-wide usage.
It is **not** the key you hand out to students.

## 2. Wire in the benchmarked PCs

`litellm_config.yaml`'s `model_list` is hand-edited today, one entry per
(PC, model, route). Once a PC has run `benchmark/run_benchmark.py` and
written `results/<hostname>.json`, run:

```bash
python orchestrator/generate_config.py > /tmp/model_list.yaml
```

Review the output, then paste it over the `model_list:` block in
`litellm_config.yaml` and `docker compose restart proxy`. This stays a
manual review step on purpose — a bad benchmark run shouldn't be able to
silently reconfigure a proxy other people are actively using.

## 3. Issuing per-user keys

Each person gets their own virtual key, scoped and budgeted, minted with
the master key:

```bash
curl -X POST http://<gateway-host>:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "models": ["coding-agent", "text-agent", "vision-agent"],
        "max_budget": 20,
        "duration": "30d",
        "metadata": {"user": "student-jdoe"}
      }'
```

Returns `{"key": "sk-...", ...}`. That `sk-...` is what you send the
student/professor — it only works against the `models` list you gave it,
resets/expires per `duration`, and every call against it is logged against
`metadata.user`, so usage per person is always attributable without anyone
sharing the master key. Revoke with `POST /key/delete`.

## 4. Pointing clients at it

**Claude Code** (LiteLLM proxy speaks the Anthropic `/v1/messages` shape
too, not just OpenAI's):

```bash
export ANTHROPIC_BASE_URL=http://<gateway-host>:4000
export ANTHROPIC_API_KEY=sk-...   # the per-user key from step 3
```

**Any OpenAI-compatible client** (ChatGPT-style UIs, `openai` SDK, etc.):

```bash
export OPENAI_BASE_URL=http://<gateway-host>:4000/v1
export OPENAI_API_KEY=sk-...
```

Then request a model by route name, e.g. `coding-agent`, exactly like any
other model name.

## Notes / honest gaps

- **Not yet deployed.** This is the config/compose scaffold only — nobody
  has run `docker compose up` against a real gateway host yet, and
  `litellm_config.yaml`'s single G014-01 entry is a placeholder pointing at
  a model tag that hasn't been benchmark-confirmed as the winner for that
  box. Treat every hostname/tag in this file as "to be replaced."
- **`g014-01.lab.uiw.edu` is a guessed hostname pattern**, not a confirmed
  one — swap in whatever the lab PCs actually resolve as (or hardcode IPs)
  before deploying.
- **CORS/network exposure**: this gateway will be reachable by anyone on
  whatever network segment it's bound to. Bind it to the lab's internal
  network only, not a public interface, unless you've thought through
  exposing it further.
