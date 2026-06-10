"""Hayward — a thin litellm-proxy gateway fronted by asfquart for the ASF.

Phase 1: ASF identity + per-PMC budgets + manual model choice, served at
llm.apache.org. asfquart owns identity/authz; litellm owns the catalog,
budgets, metering, and the OpenAI-compatible API. This package is the seam
between them plus a thin portal.
"""

__version__ = "0.1.0"
