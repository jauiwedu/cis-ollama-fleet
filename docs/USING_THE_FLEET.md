# Using the CIS AI fleet

This gives you your own API key to the lab's AI models, backed by the CIS
lab GPUs. Access is limited to Workstudy, Faculty, and Professors (checked
against your AD group membership) — you log in with your normal AD
username and password, nothing new to remember.

## 1. Log in and get your key

1. Go to `<PROXY_BASE_URL>` (ask your admin for this URL — it's the CIS AI
   fleet's login page).
2. Click **Login with SSO**, sign in with your AD username/password.
   - If you're not in Workstudy, Faculty, or Professors, this will be
     rejected at login — that's the group check, contact CIS if you believe
     this is wrong.
3. Once logged in, go to **Keys** → **Create Key**.
4. Give it a name (e.g. "my laptop"), leave the model list as-is (it's
   already scoped to what your group can use), and create it.
5. Copy the key — it starts with `sk-...` and is shown once. Store it
   somewhere private (a password manager, not a shared doc or chat).

Treat this key like a password: anyone with it can use your budget and
their usage is attributed to your account.

## 2. Available models

| Route name | What it is | Notes |
|---|---|---|
| `general-agent` | General-purpose chat/coding model (Phi-4 Mini, low-refusal-tuned) | Fastest model in the fleet, good default choice |

More routes get added as more lab PCs come online — check back here or ask
your admin what's currently available.

## 3. Using your key

### Claude Code

```bash
export ANTHROPIC_BASE_URL=<PROXY_BASE_URL>
export ANTHROPIC_API_KEY=sk-...   # your key from step 1
```

Then run `claude` as normal — it talks to the fleet instead of Anthropic's
API. Model selection follows the route names in the table above.

### Any OpenAI-compatible tool (ChatGPT-style UIs, the `openai` Python SDK, etc.)

```bash
export OPENAI_BASE_URL=<PROXY_BASE_URL>/v1
export OPENAI_API_KEY=sk-...
```

```python
from openai import OpenAI
client = OpenAI(base_url="<PROXY_BASE_URL>/v1", api_key="sk-...")

resp = client.chat.completions.create(
    model="general-agent",
    messages=[{"role": "user", "content": "explain how TCP handshakes work"}],
)
print(resp.choices[0].message.content)
```

### Plain curl

```bash
curl <PROXY_BASE_URL>/v1/chat/completions \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{
        "model": "general-agent",
        "messages": [{"role": "user", "content": "hello"}]
      }'
```

## 4. Checking your usage/budget

Back in the proxy UI (same login as step 1) → **Usage** shows your spend
and remaining budget for the current period. If you hit your budget cap,
requests will start failing until it resets (or ask your admin to raise it).

## 5. Problems

- **"Login with SSO" fails immediately** — you're either not in one of the
  three AD groups, or your AD password is wrong. Not a fleet bug.
- **401/403 on API calls** — your key may have expired or been revoked;
  generate a new one from the UI.
- **429 / budget errors** — you've hit your budget cap for the period.
- **Model unavailable** — the lab PC hosting it may be off or asleep;
  report the specific route name (e.g. `general-agent`) to your admin.

This is a security-research/education deployment — the models here are
intentionally lower-refusal than mainstream hosted assistants for that
purpose. Use accordingly and within your program's acceptable-use policy.
