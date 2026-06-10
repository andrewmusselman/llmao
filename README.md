# Hayward

A thin **litellm-proxy gateway fronted by asfquart**, served at `llm.apache.org`.
This is **Phase 1**: ASF identity, per-PMC budgets, a model catalog with
governance metadata, and manual model selection — text or file in, metered
response out.

asfquart owns identity and per-PMC authorization. litellm owns the catalog,
budgets, metering, and the OpenAI-compatible API. The code in this repo is the
**seam** between them, plus a thin portal.

```
ASF id ──oauth/JWT──►  asfquart front  ──team key──►  litellm proxy ──►  models
                       (who you are,                  (what it cost,      (external +
                        what PMCs)                      per-team budget)    self-host)
```

---

## Quickstart (no external services)

Runs out of the box in **dev mode** (stub login) with a **mock LLM backend**,
so you can click through the whole flow on a laptop.

```bash
make install        # creates a local .venv and installs deps into it
make run            # serves http://127.0.0.1:8080
```

`make` builds an isolated `.venv` so it works on Debian/Ubuntu's
"externally managed" Python (PEP 668) without touching your system packages.
If you'd rather manage the environment yourself:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m hayward.app
```

Open <http://127.0.0.1:8080>, click **Sign in (dev)**, and stand in as an
identity — e.g. uid `jdoe`, projects `airflow, lineage`, PMC `airflow`. Then:

- pick a model (note the license / openness / provenance shown inline),
- type a prompt or attach a text/code file,
- **Send** — the call is metered and billed to the selected project,
- watch the **Budget & activity** panel update (activity is visible to PMC
  members of the project).

Run the tests:

```bash
make test          # 9 tests: seam, budgets, authz, catalog, HTTP API
```

---

## What Phase 1 includes

| Capability | Where it lives | Notes |
|---|---|---|
| ASF login + PMC authz | `auth.py` + asfquart (prod) | dev-stub mirrors asfquart's `ClientSession` shape |
| Per-PMC budgets & spend | litellm teams (prod) / `MockBackend` (dev) | one litellm *team* per ASF project |
| Project ↔ team mapping | `seam.py` | the one real piece of Phase 1 code |
| Model catalog + governance metadata | `catalog.py` | license, openness, weights, provenance (explicit) |
| OpenAI-compatible chat API | `app.py` `/v1/chat/completions` | text or uploaded file |
| Per-project activity view | `app.py` `/v1/projects/<p>/usage` | PMC admins / site admins only |
| Thin portal | `portal.py` | single self-contained page, no build step |

**Deferred to later phases:** input scanning (Phase 2), automatic routing
(Phase 3), benchmarking (Phase 4). Models are chosen by hand in Phase 1.

---

## API

All endpoints require an authenticated session (cookie) or, in asf mode, a
bearer PAT. The chat endpoint is OpenAI-shaped, so existing clients work by
changing the base URL.

```bash
# List approved models (with governance metadata under `.hayward`)
GET /v1/models

# Chat. The billed project comes from the X-Hayward-Project header,
# the body's "project", or (if you're on exactly one) your sole project.
POST /v1/chat/completions
  { "model": "openai/gpt-4o-mini", "messages": [{"role":"user","content":"hi"}] }

# Per-project budget (members) and activity (PMC admins)
GET /v1/projects/<project>/budget
GET /v1/projects/<project>/usage
```

Errors use standard codes: `401` unauthenticated, `403` not a member / not a
PMC admin, `404` unknown model, `429` project budget exceeded.

---

## Production

Two environment flips move from the laptop demo to the real thing:

```bash
export HAYWARD_AUTH_MODE=asf          # oauth.apache.org + LDAP via asfquart
export HAYWARD_LITELLM_MODE=proxy     # talk to a real litellm proxy
```

1. **Install asfquart** (provides the OAuth gateway at `/auth`, JWT/PAT, and
   LDAP-backed sessions): see
   <https://github.com/apache/infrastructure-asfquart>. In asf mode the app is
   built with `asfquart.construct("hayward")`, so login and PMC membership come
   from real ASF identity.

2. **Run the litellm proxy** with the generated config:

   ```bash
   make config        # regenerate litellm/config.yaml from the catalog
   make proxy         # litellm --config litellm/config.yaml
   ```

   Set `HAYWARD_SELFHOST_BASE_URL` to your vast.ai vLLM endpoint and the
   provider keys (`OPENAI_API_KEY`, etc.). Set `HAYWARD_LITELLM_MASTER_KEY` to
   the same value as the proxy's `master_key`; the seam uses it to provision
   teams and mint per-team keys.

3. **Serve** behind hypercorn and point DNS/TLS for `llm.apache.org` at it.

The PAT handler in `auth.py` (`make_token_handler`) is a stub: wire it to your
token store to let non-interactive CLI/SDK callers authenticate.

---

## The catalog is the source of truth

`hayward/catalog.py` defines the models and their governance metadata. The
litellm proxy config is generated from it (`scripts/render_litellm_config.py`),
so the portal's list and the proxy's routes never drift. Add a model by adding
a `CatalogModel`, then `make config`.

---

## Layout

```
hayward/
  app.py            app factory + routes (dev: plain Quart; prod: asfquart)
  seam.py           ASF project -> litellm team; authz; metered chat
  auth.py           identity resolution (asfquart session/PAT or dev stub)
  litellm_client.py ProxyBackend (real) + MockBackend (dev), one interface
  catalog.py        models + license/openness/weights/provenance
  portal.py         the single-page portal
  store.py          tiny JSON state store (swap for a DB later)
  config.py         env-driven settings
litellm/config.yaml litellm proxy config (generated)
scripts/            config renderer
tests/              Phase 1 test suite
```
