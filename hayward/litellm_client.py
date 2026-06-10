"""litellm backend abstraction.

Two implementations behind one interface:

* ``ProxyBackend`` talks to a real litellm proxy. It uses the proxy's admin
  endpoints (/team/new, /key/generate, /team/info) to provision a team and
  mint a scoped key for each ASF project — this is how per-PMC budgets and
  spend tracking happen natively — and forwards chat to /v1/chat/completions
  with that team key.

* ``MockBackend`` fakes all of the above in-process so the app runs with no
  litellm proxy at all (laptop demos, CI). It tracks per-team spend in the
  StateStore using a crude token-count cost model, so budgets and the activity
  view are exercised end to end.

The seam (seam.py) depends only on this interface, so flipping
HAYWARD_LITELLM_MODE from "mock" to "proxy" changes nothing upstream.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

from .config import Settings
from .store import StateStore


class BudgetExceeded(Exception):
    """Raised when a team is over budget (mirrors litellm proxy's 4xx)."""


@dataclass
class Completion:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


@dataclass
class TeamInfo:
    team_id: str
    key: str
    max_budget: float
    spend: float


class Backend(Protocol):
    def ensure_team(self, project: str, budget_usd: float, duration: str) -> TeamInfo: ...
    def team_info(self, project: str) -> Optional[TeamInfo]: ...
    def chat(self, project: str, model_backend: str, messages: List[Dict], params: Dict) -> Completion: ...
    def usage(self, project: Optional[str]) -> List[Dict]: ...


# ---------------------------------------------------------------------------
# Mock backend — no network, used for local/dev/CI.
# ---------------------------------------------------------------------------

def _est_tokens(text: str) -> int:
    # ~4 chars/token is good enough for a demo cost model.
    return max(1, len(text) // 4)


# Rough per-1k-token USD pricing so the budget math is non-trivial.
_MOCK_PRICES = {
    "openai/llama-3.1-8b-instruct": 0.0,      # self-hosted: no marginal API cost
    "openai/mistral-7b-instruct": 0.0,
    "openai/gpt-4o-mini": 0.0006,
    "anthropic/claude-haiku-4-5": 0.0010,
}


class MockBackend:
    def __init__(self, settings: Settings, store: StateStore):
        self._s = settings
        self._store = store

    def ensure_team(self, project: str, budget_usd: float, duration: str) -> TeamInfo:
        def _mut(data):
            teams = data.setdefault("teams", {})
            if project not in teams:
                teams[project] = {
                    "team_id": f"team-{uuid.uuid4().hex[:12]}",
                    "key": f"sk-team-{uuid.uuid4().hex[:24]}",
                    "max_budget": budget_usd,
                    "spend": 0.0,
                    "duration": duration,
                    "created_at": time.time(),
                }
            t = teams[project]
            return TeamInfo(t["team_id"], t["key"], t["max_budget"], t["spend"])
        return self._store.update(_mut)

    def team_info(self, project: str) -> Optional[TeamInfo]:
        teams = self._store.snapshot().get("teams", {})
        t = teams.get(project)
        if not t:
            return None
        return TeamInfo(t["team_id"], t["key"], t["max_budget"], t["spend"])

    def chat(self, project: str, model_backend: str, messages: List[Dict], params: Dict) -> Completion:
        prompt_text = "\n".join(m.get("content", "") for m in messages)
        prompt_tokens = _est_tokens(prompt_text)

        # Pre-flight budget check against the team's remaining allowance.
        info = self.team_info(project)
        if info is not None and info.max_budget > 0 and info.spend >= info.max_budget:
            raise BudgetExceeded(f"team for {project} is over budget ({info.spend:.4f}/{info.max_budget:.2f} USD)")

        # Deterministic, clearly-fake completion so demos are legible.
        last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        reply = (
            f"[mock:{model_backend}] Received {prompt_tokens} prompt tokens. "
            f"Echoing intent: {last_user[:160]}"
        )
        completion_tokens = _est_tokens(reply)
        price = _MOCK_PRICES.get(model_backend, 0.0005)
        cost = round((prompt_tokens + completion_tokens) / 1000.0 * price, 6)

        def _mut(data):
            teams = data.setdefault("teams", {})
            if project in teams:
                teams[project]["spend"] = round(teams[project].get("spend", 0.0) + cost, 6)
            data.setdefault("usage", []).append({
                "ts": time.time(),
                "project": project,
                "model": model_backend,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": cost,
            })
        self._store.update(_mut)

        return Completion(reply, model_backend, prompt_tokens, completion_tokens, cost)

    def usage(self, project: Optional[str]) -> List[Dict]:
        rows = self._store.snapshot().get("usage", [])
        if project is None:
            return list(rows)
        return [r for r in rows if r.get("project") == project]


# ---------------------------------------------------------------------------
# Proxy backend — real litellm proxy over HTTP.
# ---------------------------------------------------------------------------

class ProxyBackend:
    """Talks to a running litellm proxy. Requires `requests`.

    Team provisioning uses the proxy admin API with the master key; chat uses
    the per-team key so the proxy attributes spend to the team automatically.
    """

    def __init__(self, settings: Settings, store: StateStore):
        self._s = settings
        self._store = store
        import requests  # local import so mock mode needs no dependency
        self._requests = requests

    def _admin_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._s.litellm_master_key}", "Content-Type": "application/json"}

    def ensure_team(self, project: str, budget_usd: float, duration: str) -> TeamInfo:
        existing = self.team_info(project)
        if existing:
            return existing

        base = self._s.litellm_base_url.rstrip("/")
        # 1. Create a team scoped to this ASF project with a budget.
        team_resp = self._requests.post(
            f"{base}/team/new",
            json={"team_alias": project, "max_budget": budget_usd, "budget_duration": duration},
            headers=self._admin_headers(), timeout=15,
        )
        team_resp.raise_for_status()
        team_id = team_resp.json().get("team_id")

        # 2. Mint a key bound to that team.
        key_resp = self._requests.post(
            f"{base}/key/generate",
            json={"team_id": team_id, "key_alias": f"hayward-{project}"},
            headers=self._admin_headers(), timeout=15,
        )
        key_resp.raise_for_status()
        key = key_resp.json().get("key")

        def _mut(data):
            data.setdefault("teams", {})[project] = {
                "team_id": team_id, "key": key,
                "max_budget": budget_usd, "spend": 0.0,
                "duration": duration, "created_at": time.time(),
            }
        self._store.update(_mut)
        return TeamInfo(team_id, key, budget_usd, 0.0)

    def team_info(self, project: str) -> Optional[TeamInfo]:
        t = self._store.snapshot().get("teams", {}).get(project)
        if not t:
            return None
        # Refresh spend from the proxy when possible.
        spend = t.get("spend", 0.0)
        try:
            base = self._s.litellm_base_url.rstrip("/")
            resp = self._requests.get(
                f"{base}/team/info", params={"team_id": t["team_id"]},
                headers=self._admin_headers(), timeout=10,
            )
            if resp.ok:
                spend = resp.json().get("team_info", {}).get("spend", spend)
        except Exception:
            pass
        return TeamInfo(t["team_id"], t["key"], t.get("max_budget", 0.0), spend)

    def chat(self, project: str, model_backend: str, messages: List[Dict], params: Dict) -> Completion:
        info = self.team_info(project)
        if info is None:
            raise RuntimeError(f"no litellm team provisioned for {project}")
        base = self._s.litellm_base_url.rstrip("/")
        payload = {"model": model_backend, "messages": messages, **params}
        resp = self._requests.post(
            f"{base}/v1/chat/completions", json=payload,
            headers={"Authorization": f"Bearer {info.key}", "Content-Type": "application/json"},
            timeout=120,
        )
        if resp.status_code in (400, 402, 429) and "budget" in resp.text.lower():
            raise BudgetExceeded(resp.text)
        resp.raise_for_status()
        body = resp.json()
        choice = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        cost = float(body.get("_hidden_params", {}).get("response_cost") or 0.0)

        def _mut(data):
            data.setdefault("usage", []).append({
                "ts": time.time(), "project": project, "model": model_backend,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "cost_usd": cost,
            })
        self._store.update(_mut)
        return Completion(
            choice, model_backend,
            usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), cost,
        )

    def usage(self, project: Optional[str]) -> List[Dict]:
        rows = self._store.snapshot().get("usage", [])
        if project is None:
            return list(rows)
        return [r for r in rows if r.get("project") == project]


def make_backend(settings: Settings, store: StateStore) -> Backend:
    if settings.is_mock_llm:
        return MockBackend(settings, store)
    return ProxyBackend(settings, store)
