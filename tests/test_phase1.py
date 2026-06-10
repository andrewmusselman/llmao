"""Phase 1 tests: the seam, budget enforcement, authz, catalog, and the HTTP API.

Run with: pytest -q
These exercise the mock backend so no litellm proxy or ASF auth is needed.
"""
import asyncio
import os
import tempfile

import pytest

from hayward.config import Settings
from hayward.store import StateStore
from hayward.litellm_client import MockBackend, BudgetExceeded
from hayward.seam import Seam, Identity, AuthzError, CatalogError
from hayward import catalog


def _settings(tmp):
    return Settings(
        auth_mode="dev",
        litellm_mode="mock",
        state_path=os.path.join(tmp, "state.json"),
        default_team_budget_usd=0.05,
        site_admins=["root"],
    )


def _seam(tmp):
    s = _settings(tmp)
    store = StateStore(s.state_path)
    return Seam(s, MockBackend(s, store)), s


def test_catalog_has_governance_metadata():
    for m in catalog.all_models():
        assert m["license"]
        assert m["openness"] in ("open-weight", "open-source", "proprietary")
        assert m["provenance_record"] in ("present", "absent")


def test_member_can_call_and_is_metered():
    with tempfile.TemporaryDirectory() as tmp:
        seam, _ = _seam(tmp)
        ident = Identity(uid="jdoe", projects=["airflow"], committees=[])
        c = seam.chat(ident, "airflow", "openai/gpt-4o-mini", [{"role": "user", "content": "hi there"}])
        assert c.content
        assert c.prompt_tokens > 0
        info = seam.team_status("airflow")
        assert info is not None
        assert info.spend >= 0.0


def test_non_member_is_refused():
    with tempfile.TemporaryDirectory() as tmp:
        seam, _ = _seam(tmp)
        ident = Identity(uid="jdoe", projects=["airflow"], committees=[])
        with pytest.raises(AuthzError):
            seam.chat(ident, "kafka", "openai/gpt-4o-mini", [{"role": "user", "content": "hi"}])


def test_unknown_model_is_refused():
    with tempfile.TemporaryDirectory() as tmp:
        seam, _ = _seam(tmp)
        ident = Identity(uid="jdoe", projects=["airflow"], committees=[])
        with pytest.raises(CatalogError):
            seam.chat(ident, "airflow", "no/such-model", [{"role": "user", "content": "hi"}])


def test_budget_is_enforced():
    with tempfile.TemporaryDirectory() as tmp:
        seam, _ = _seam(tmp)
        ident = Identity(uid="jdoe", projects=["airflow"], committees=[])
        # Budget is tiny ($0.05). Hammer a priced (external) model until it trips.
        tripped = False
        for _ in range(500):
            try:
                seam.chat(ident, "airflow", "anthropic/claude-haiku",
                          [{"role": "user", "content": "x" * 4000}])
            except BudgetExceeded:
                tripped = True
                break
        assert tripped, "expected the budget to be exceeded"


def test_activity_requires_pmc_admin():
    with tempfile.TemporaryDirectory() as tmp:
        seam, _ = _seam(tmp)
        member = Identity(uid="jdoe", projects=["airflow"], committees=[])
        admin = Identity(uid="chair", projects=[], committees=["airflow"])
        seam.chat(member, "airflow", "openai/gpt-4o-mini", [{"role": "user", "content": "hi"}])
        with pytest.raises(AuthzError):
            seam.project_activity(member, "airflow")
        rows = seam.project_activity(admin, "airflow")
        assert len(rows) == 1


def test_site_admin_sees_any_project():
    with tempfile.TemporaryDirectory() as tmp:
        seam, _ = _seam(tmp)
        member = Identity(uid="jdoe", projects=["airflow"], committees=[])
        root = Identity(uid="root", projects=[], committees=[], is_site_admin=True)
        seam.chat(member, "airflow", "openai/gpt-4o-mini", [{"role": "user", "content": "hi"}])
        rows = seam.project_activity(root, "airflow")
        assert len(rows) == 1


# -- HTTP-level smoke test --------------------------------------------------

def test_http_chat_flow():
    with tempfile.TemporaryDirectory() as tmp:
        s = _settings(tmp)
        from hayward.app import create_app
        app = create_app(s)

        async def run():
            client = app.test_client()
            # dev login as a committer on airflow
            await client.post("/auth/dev/login", form={"uid": "jdoe", "projects": "airflow", "committees": ""})
            # list models (authed)
            r = await client.get("/v1/models")
            assert r.status_code == 200
            # chat
            r = await client.post("/v1/chat/completions", json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": "hello"}],
            }, headers={"X-Hayward-Project": "airflow"})
            assert r.status_code == 200, await r.get_data()
            body = await r.get_json()
            assert body["choices"][0]["message"]["content"]
            assert body["hayward_project"] == "airflow"
            # budget reflects the spend
            r = await client.get("/v1/projects/airflow/budget")
            b = await r.get_json()
            assert b["provisioned"] is True

        asyncio.run(run())


def test_http_requires_auth():
    with tempfile.TemporaryDirectory() as tmp:
        s = _settings(tmp)
        from hayward.app import create_app
        app = create_app(s)

        async def run():
            client = app.test_client()
            r = await client.post("/v1/chat/completions", json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
            })
            assert r.status_code == 401

        asyncio.run(run())
