#!/usr/bin/env python3
"""Render litellm/config.yaml from the Hayward catalog.

The catalog (hayward/catalog.py) is the single source of truth for which models
exist and what their backend strings are. This script emits a litellm proxy
model_list that matches, so the two never drift.

Usage:
    python scripts/render_litellm_config.py > litellm/config.yaml
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hayward import catalog


HEADER = """# litellm proxy configuration for Hayward — GENERATED from hayward/catalog.py.
# Edit the catalog, then re-run scripts/render_litellm_config.py.

model_list:
"""

SELFHOST_BLOCK = """  - model_name: {backend}
    litellm_params:
      model: {backend}
      api_base: os.environ/HAYWARD_SELFHOST_BASE_URL
      api_key: os.environ/HAYWARD_SELFHOST_API_KEY
"""

EXTERNAL_BLOCK = """  - model_name: {backend}
    litellm_params:
      model: {backend}
      api_key: os.environ/{env}
"""

PROVIDER_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "bedrock": "AWS_BEARER_TOKEN_BEDROCK",
}

FOOTER = """
litellm_settings:
  drop_params: true
  success_callback: ["litellm_spend_logs"]

general_settings:
  master_key: os.environ/HAYWARD_LITELLM_MASTER_KEY
"""


def main():
    out = [HEADER]
    for m in catalog.CATALOG:
        if m.self_hosted:
            out.append(SELFHOST_BLOCK.format(backend=m.backend))
        else:
            env = PROVIDER_ENV.get(m.provider, f"{m.provider.upper()}_API_KEY")
            out.append(EXTERNAL_BLOCK.format(backend=m.backend, env=env))
    out.append(FOOTER)
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
