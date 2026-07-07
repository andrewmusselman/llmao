#!/usr/bin/env python3
"""Render litellm/config.yaml from the llmao catalog.

The catalog (llmao/catalog.py) is the single source of truth for which models
exist and what their backend strings are. This script emits a litellm proxy
model_list that matches, so the two never drift.

Self-hosted models each carry their own ``api_base_env`` so litellm can fan out
to a per-model vLLM server (one vLLM process per model, each on its own port).
This is Option A: litellm routes by model_name to the right vLLM container,
with no wake latency between models.

Usage:
    python scripts/render_litellm_config.py > litellm/config.yaml
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llmao import catalog


HEADER = """# litellm proxy configuration for llmao — GENERATED from llmao/catalog.py.
# Edit the catalog, then re-run scripts/render_litellm_config.py.

model_list:
"""

# Self-hosted models point at a per-model vLLM server. Each entry's
# api_base env var is derived from its backend (see catalog.api_base_env).
SELFHOST_BLOCK = """  - model_name: {backend}
    litellm_params:
      model: openai/{served_name}
      api_base: os.environ/{api_base_env}
      api_key: os.environ/LLMAO_SELFHOST_API_KEY
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
  master_key: os.environ/LLMAO_LITELLM_MASTER_KEY
"""


def main():
    out = [HEADER]
    for m in catalog.CATALOG:
        if m.self_hosted:
            out.append(SELFHOST_BLOCK.format(
                backend=m.backend,
                served_name=m.served_name,
                api_base_env=m.api_base_env,
            ))
        else:
            env = PROVIDER_ENV.get(m.provider, f"{m.provider.upper()}_API_KEY")
            out.append(EXTERNAL_BLOCK.format(backend=m.backend, env=env))
    out.append(FOOTER)
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
