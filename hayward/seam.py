"""The seam — the one piece of real Phase 1 code.

asfquart tells us *who the user is and what projects they're on*. litellm tells
us *what it cost*. The seam is the join: it resolves an ASF project to a litellm
team (provisioning the team with a budget on first use), authorizes that the
calling identity is actually a member of the project it wants to bill, and runs
the metered chat through the backend.

Keeping the ASF-project <-> litellm-team mapping correct as membership changes
is the substance flagged in the plan as "the part that isn't free."
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from . import catalog
from .config import Settings
from .litellm_client import Backend, BudgetExceeded, Completion, TeamInfo


class AuthzError(Exception):
    """Caller is not a member of the project they tried to use."""


class CatalogError(Exception):
    """Requested model is not in the catalog."""


@dataclass
class Identity:
    """The subset of an asfquart ClientSession the seam needs."""
    uid: str
    projects: List[str]      # committer projects
    committees: List[str]    # PMC memberships (admin within those projects)
    is_site_admin: bool = False

    def member_of(self, project: str) -> bool:
        return project in self.projects or project in self.committees

    def admin_of(self, project: str) -> bool:
        return self.is_site_admin or project in self.committees


class Seam:
    def __init__(self, settings: Settings, backend: Backend):
        self._s = settings
        self._backend = backend

    # -- project / team resolution ----------------------------------------

    def ensure_project_team(self, project: str) -> TeamInfo:
        """Resolve (provisioning if needed) the litellm team for an ASF project."""
        return self._backend.ensure_team(
            project,
            budget_usd=self._s.default_team_budget_usd,
            duration=self._s.budget_duration,
        )

    def team_status(self, project: str) -> Optional[TeamInfo]:
        return self._backend.team_info(project)

    # -- the metered, authorized call -------------------------------------

    def chat(
        self,
        identity: Identity,
        project: str,
        model_id: str,
        messages: List[Dict],
        params: Optional[Dict] = None,
    ) -> Completion:
        # 1. Authorization: the identity must belong to the project it bills.
        if not (identity.is_site_admin or identity.member_of(project)):
            raise AuthzError(f"{identity.uid} is not a member of {project}")

        # 2. Catalog: only approved models are callable.
        model = catalog.get(model_id)
        if model is None:
            raise CatalogError(f"unknown model {model_id!r}")

        # 3. Ensure the team exists (provisions budget on first use).
        self.ensure_project_team(project)

        # 4. Metered call through litellm (budget enforced in the backend).
        return self._backend.chat(project, model.backend, messages, params or {})

    # -- activity view ----------------------------------------------------

    def project_activity(self, identity: Identity, project: str) -> List[Dict]:
        """Everyone's activity in a project. PMC admins (or site admins) only."""
        if not identity.admin_of(project):
            raise AuthzError(f"{identity.uid} is not a PMC admin of {project}")
        return self._backend.usage(project)
