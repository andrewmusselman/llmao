"""Authentication / identity resolution.

In production (HAYWARD_AUTH_MODE=asf) this reads a real asfquart
``ClientSession`` — populated by oauth.apache.org + LDAP — and also supports
bearer PATs through asfquart's ``token_handler`` hook. In dev mode it issues a
stub session from a simple login form so the whole app is runnable with no
external services. Both paths produce the same :class:`~hayward.seam.Identity`,
so nothing downstream branches on auth mode.
"""
from __future__ import annotations

from typing import List, Optional

from quart import request, session as quart_session

from .config import Settings
from .seam import Identity

# Cookie key for the dev-stub session.
_DEV_SESSION_KEY = "hayward_dev_session"


# ---------------------------------------------------------------------------
# Dev-stub auth
# ---------------------------------------------------------------------------

def dev_login(uid: str, projects: List[str], committees: List[str]) -> None:
    quart_session[_DEV_SESSION_KEY] = {
        "uid": uid,
        "projects": projects,
        "committees": committees,
    }


def dev_logout() -> None:
    quart_session.pop(_DEV_SESSION_KEY, None)


def _identity_from_dev(settings: Settings) -> Optional[Identity]:
    raw = quart_session.get(_DEV_SESSION_KEY)
    if not raw:
        return None
    return Identity(
        uid=raw["uid"],
        projects=list(raw.get("projects", [])),
        committees=list(raw.get("committees", [])),
        is_site_admin=raw["uid"] in settings.site_admins,
    )


# ---------------------------------------------------------------------------
# Real asfquart auth
# ---------------------------------------------------------------------------

async def _identity_from_asfquart(settings: Settings) -> Optional[Identity]:
    # Imported lazily so dev mode doesn't require asfquart installed.
    import asfquart.session as asf_session

    client_session = await asf_session.read()
    if client_session is None or not getattr(client_session, "uid", None):
        return None
    return Identity(
        uid=client_session.uid,
        projects=list(getattr(client_session, "projects", []) or []),
        committees=list(getattr(client_session, "committees", []) or []),
        is_site_admin=(
            client_session.uid in settings.site_admins
            or bool(getattr(client_session, "isRoot", False))
        ),
    )


# ---------------------------------------------------------------------------
# Unified resolver
# ---------------------------------------------------------------------------

async def current_identity(settings: Settings) -> Optional[Identity]:
    """Resolve the calling identity regardless of auth mode.

    Order: an Authorization bearer token (PAT) is tried first in asf mode so
    non-interactive SDK/CLI callers work; otherwise the cookie session.
    """
    if settings.is_dev_auth:
        # Dev mode still honours a simple bearer token for API testing:
        # "Bearer dev:<uid>:<proj1|proj2>:<pmc1|pmc2>".
        token = _bearer_token()
        if token and token.startswith("dev:"):
            try:
                _, uid, projs, pmcs = token.split(":", 3)
                return Identity(
                    uid=uid,
                    projects=[p for p in projs.split("|") if p],
                    committees=[c for c in pmcs.split("|") if c],
                    is_site_admin=uid in settings.site_admins,
                )
            except ValueError:
                return None
        return _identity_from_dev(settings)
    return await _identity_from_asfquart(settings)


def _bearer_token() -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


# ---------------------------------------------------------------------------
# asfquart PAT handler (registered on the app in asf mode)
# ---------------------------------------------------------------------------

def make_token_handler(settings: Settings):
    """Return an asfquart token_handler that maps a PAT to a session dict.

    Phase 1 ships a placeholder: PATs must be provisioned out of band and
    resolved here (e.g. from a secrets store keyed by token hash). The shape
    matches what asfquart's ``ClientSession`` expects: uid, pmcs, projects.
    """
    async def token_handler(token: str):
        # TODO Phase 1.x: look the token up in the PAT store and return its
        # bound identity. Returning None falls through to "no session".
        return None
    return token_handler
