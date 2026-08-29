# Admin guide: AD-gated login for the CIS Ollama fleet

Goal: staff/workstudy log into the LiteLLM proxy's UI with their normal
**AD username and password**, and only get in if they're a member of one of
three AD groups (Workstudy, Faculty, Professors). Once logged in, they
generate their own API key from the UI — no admin has to hand-mint keys.

LiteLLM's open-source proxy does not speak LDAP/AD directly (that's an
Enterprise-only feature). The free path is **Keycloak** sitting in front of
it: Keycloak binds to AD over LDAP and does the actual username/password
check, then hands LiteLLM a normal OIDC login — LiteLLM never sees AD
credentials at all.

```
staff/workstudy browser
        │  AD username + password
        ▼
   Keycloak (LDAP bind to AD, checks group membership)
        │  OIDC token (groups claim: Workstudy/Faculty/Professors)
        ▼
   LiteLLM Proxy UI  →  user clicks "Create Key"  →  sk-... API key
```

Confirmed directly against the domain controller (`cis-windows.cis.lab`,
`192.168.128.11`), domain `cis.lab`:

- **LDAP server address**: `cis-windows.cis.lab` (`192.168.128.11`). Plain
  LDAP is `ldap://cis-windows.cis.lab:389`. **LDAPS (636) vs. plain 389 has
  not been confirmed** — ask IT whether the DC has a valid cert for LDAPS
  before assuming 389 is acceptable for production; sending AD bind
  credentials over plain LDAP on an untrusted segment is a real risk.
- **User search base DN**: `OU=Users,OU=CIS Lab,DC=cis,DC=lab` (contains
  per-role sub-OUs `Students`, `Faculty`, `Professors`, `Workstudies`).
- **Exact group names/DNs** for the three groups this fleet gates on:
  - Workstudy → `CIS Workstudies` —
    `CN=CIS Workstudies,OU=Users,OU=CIS Lab,DC=cis,DC=lab`
  - Faculty → `CIS Faculty` —
    `CN=CIS Faculty,OU=Users,OU=CIS Lab,DC=cis,DC=lab`
  - Professors → `CIS Professors` —
    `CN=CIS Professors,OU=Users,OU=CIS Lab,DC=cis,DC=lab`

  (Note the real group names carry the "CIS " prefix and, for Workstudy, an
  "-ies" plural — don't type `Workstudy`/`Faculty`/`Professors` bare into
  Keycloak's group mapper, use the exact `CIS ...` names above.)

**Still missing — not yet obtained:**
- **Bind account** — a low-privilege, read-only AD service account for
  Keycloak to search AD with. No existing "svc-ldap"/"svc-keycloak"-style
  account was found; one will likely need to be created in AD (e.g. under
  `OU=Users,OU=CIS Lab,DC=cis,DC=lab` or a dedicated service-accounts OU) —
  that's an AD write action, so have IT create it rather than doing it ad
  hoc: `sAMAccountName`, password, and read access to
  `OU=Users,OU=CIS Lab,DC=cis,DC=lab` is all it needs. It should **not** be
  a domain admin account.
- **LDAPS confirmation** (see above).

Everything below uses the confirmed values; swap in the bind account once
IT provisions it.

## 1. Bring up the stack

```bash
cd orchestrator
cp .env.example .env
# fill in ALL values in .env, including the new Keycloak/SSO ones —
# see the comments in .env.example for what each one is
docker compose up -d
```

Keycloak's admin console is now at `http://<gateway-host>:8080`, log in with
`admin` / the `KEYCLOAK_ADMIN_PASSWORD` you set.

## 2. Create the realm

Admin console → top-left realm dropdown → **Create realm** → name it to
match `KEYCLOAK_REALM` in your `.env` (default `cis-ai-fleet`) → Create.
Stay inside this realm for every step below.

## 3. Federate to AD over LDAP

**User federation** → **Add Ldap providers**:

| Field | Value |
|---|---|
| Vendor | Active Directory |
| Connection URL | `ldap://cis-windows.cis.lab:389` (confirm LDAPS with IT first — see note above) |
| Bind DN | the service account's full DN (not yet provisioned — see above) |
| Bind credential | its password |
| Users DN | `OU=Users,OU=CIS Lab,DC=cis,DC=lab` |
| Username LDAP attribute | `sAMAccountName` |
| RDN LDAP attribute | `cn` |
| UUID LDAP attribute | `objectGUID` |
| User object classes | `person, organizationalPerson, user` |

Click **Test connection**, then **Test authentication** — fix these before
moving on, don't skip straight to "Save."

Save, then **Synchronize all users** (top of the page) once — confirms the
bind account and search base actually see your users.

## 4. Sync the three AD groups

On the LDAP provider you just made → **Mappers** tab → **Add mapper**:

- Name: `ad-groups`
- Mapper type: `group-ldap-mapper`
- LDAP Groups DN: `OU=Users,OU=CIS Lab,DC=cis,DC=lab` (the groups
  `CIS Workstudies`/`CIS Faculty`/`CIS Professors` live directly in this OU,
  same as the users)
- Group Name LDAP Attribute: `cn`
- Membership LDAP Attribute: `member`
- Mode: `READ_ONLY` (Keycloak should never write back to AD)

Save, then trigger a sync from this mapper's page. Under **Groups** (left
nav) you should now see `CIS Workstudies`, `CIS Faculty`, `CIS Professors`
(along with `CIS Students`, `CIS Capstone`, etc. — everything else in that
OU syncs too, that's expected) as top-level Keycloak groups, each populated
with the AD members.

## 5. Create one "fleet access" role and grant it to those three groups only

This is the actual gate — everything above just makes AD data visible to
Keycloak, it doesn't restrict anything yet.

1. **Realm roles** → **Create role** → name `fleet-access` → Save.
2. **Groups** → open `CIS Workstudies` → **Role mapping** → **Assign role**
   → pick `fleet-access`. Repeat for `CIS Faculty` and `CIS Professors`.
   (Leave `CIS Students`, `CIS Capstone`, and everything else unassigned —
   they synced from AD too but should not get `fleet-access`.)

Anyone in AD but *not* in one of those three groups will not carry
`fleet-access`, even though they can technically authenticate against AD.

## 6. Create the OIDC client LiteLLM will use

**Clients** → **Create client**:
- Client type: `OpenID Connect`
- Client ID: `cis-ollama-fleet` (match `GENERIC_CLIENT_ID` in `.env`)
- Next → **Client authentication: On** (makes it confidential, gives you a
  secret) → Standard flow: enabled → everything else off → Save.
- **Credentials** tab → copy the **Client secret** → paste into `.env` as
  `GENERIC_CLIENT_SECRET` → `docker compose restart proxy`.
- **Settings** tab → **Valid redirect URIs**: `<PROXY_BASE_URL>/sso/callback`
  (must match `.env`'s `PROXY_BASE_URL` exactly, including port).

### Include the fleet-access role and groups in the token

**Client scopes** → `cis-ollama-fleet-dedicated` → **Add mapper** → **By
configuration**:

- **User Realm Role** mapper: Token Claim Name `roles`, so LiteLLM (and you,
  debugging) can see `fleet-access` in the token.
- **Group Membership** mapper: Token Claim Name `groups`, Full group path:
  off. This is the `groups` claim `litellm_config.yaml`'s
  `litellm_jwtauth.team_ids_jwt_field: "groups"` reads — it's what maps a
  logged-in user onto a LiteLLM team automatically.

### Require the role to log in at all (not just to see it in the token)

**Realm settings** → **Sessions**... actually the reliable place for this in
Keycloak is a **Client Policy**: **Clients** → `cis-ollama-fleet` →
**Advanced** tab → **Authorization Details** isn't it either — use:

**Realm roles** → `fleet-access` → the role itself doesn't block login by
default; you must gate the client's authentication flow. Do this instead:
**Authentication** (left nav) → duplicate the `browser` flow (name it
`browser-fleet-gate`) → in the copy, add an execution **Conditional Role
Selector** (or **Conditional - User Role** depending on your Keycloak
version) with condition role = `fleet-access`, and set behavior to
**REQUIRED** so a user without the role gets denied at login. Bind this flow
to the `cis-ollama-fleet` client: **Clients** → `cis-ollama-fleet` →
**Advanced** → **Authentication flow overrides** → Browser Flow →
`browser-fleet-gate`.

(Keycloak's exact menu wording shifts between versions — if a step above
doesn't match what you see, search Keycloak's own docs for "conditional
role" authentication execution; the concept is the same.)

**Test before rolling out:** log in as someone in `Workstudy`/`Faculty`/
`Professors` (should succeed) and someone who is a valid AD user but *not*
in any of the three groups (should be denied at the Keycloak login screen,
not just denied inside LiteLLM).

## 7. Confirm LiteLLM picks it up

`docker compose restart proxy`, then visit `<PROXY_BASE_URL>` — you should
see a "Login with SSO" option. Log in as a test Workstudy/Faculty/Professor
account. On first login LiteLLM creates that person as an `internal_user`
(per `default_internal_user_params` in `litellm_config.yaml`) with no model
access until they're on a team — see the next section.

## 8. Give the three groups access to the fleet's models

Right now `default_internal_user_params.models: ["no-default-models"]`
means a fresh SSO login has zero model access until they're attached to a
team. Create one team per group (or one shared team for all three) via the
proxy UI or API:

```bash
curl -X POST $PROXY_BASE_URL/team/new \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "team_alias": "fleet-users",
        "team_id": "CIS Workstudies",
        "models": ["general-agent"],
        "max_budget": 20,
        "budget_duration": "30d"
      }'
```

`team_id` here must match the Keycloak group name coming through in the
`groups` claim exactly — i.e. `CIS Workstudies`, `CIS Faculty`,
`CIS Professors` (with the "CIS " prefix, not the short names) — that's
what `team_ids_jwt_field: "groups"` matches against to auto-add a
logging-in user to the right team. Repeat for `CIS Faculty` and
`CIS Professors` (same `models`, or different budgets/model lists per group
if you want staff and workstudy on different limits).

From here, hand people [docs/USING_THE_FLEET.md](USING_THE_FLEET.md) — that's
the part they actually need.
