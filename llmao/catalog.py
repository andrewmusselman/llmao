"""llmao model catalog.

Phase 1 keeps the catalog as a small in-code registry. Each entry carries the
metadata the llmao proposal requires that ordinary model cards omit:
licensing, openness, weights distribution, and training-data provenance — with
``provenance_record`` made explicit so an absent record is a field, not a
silent gap. In Phase 4 these fields get sourced from Apache Lineage; for now
they are hand-curated.

Self-host entries map to per-model vLLM servers via the litellm proxy (see
litellm/config.yaml). The ``backend`` string of each entry MUST equal a
``model_name`` in that config. For self-hosted models, ``served_name`` is the
model name vLLM answers to (its ``--served-model-name``) and ``api_base_env``
is the environment variable holding that model's vLLM base URL — one vLLM
process per model, each on its own port (Option A routing).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class CatalogModel:
    id: str
    display_name: str
    provider: str                 # external provider or "self-host"
    backend: str                  # must match a litellm model_name
    context_window: int

    # --- proposal-required governance metadata ---------------------------
    license: str
    openness: str                 # "open-weight" | "open-source" | "proprietary"
    weights_distribution: str
    training_data_provenance: str
    provenance_record: str        # "present" | "absent" — explicit, never silent

    self_hosted: bool = False
    modality: str = "text"        # "text" | "text+vision"
    notes: Optional[str] = None

    # --- self-host serving details (unused for external providers) -------
    served_name: Optional[str] = None    # vLLM --served-model-name
    api_base_env: Optional[str] = None   # env var holding this model's vLLM URL

    # --- thinking / extended reasoning -----------------------------------
    # supports_thinking: the served model runs a reasoning parser, so the
    #   enable_thinking chat-template kwarg is meaningful. False hides the
    #   toggle in the portal and the kwarg is never sent.
    #
    # thinks_by_default: what the model does with NO kwarg. Differs per model
    #   and is not guessable -- measured 2026-08-04 through the proxy:
    #     qwen3-8b   with no kwarg -> 893 chars of reasoning  (True)
    #     gemma4-26b with no kwarg -> 0 chars                 (False)
    #   Gemma reasons only when asked; Qwen reasons unless told not to. A
    #   single global default would be wrong for one of them.
    supports_thinking: bool = False
    thinks_by_default: bool = False

    def public(self) -> Dict:
        d = asdict(self)
        # Serving details are operational, not part of the public catalog.
        d.pop("served_name", None)
        d.pop("api_base_env", None)
        return d


# Phase 1 seed catalog. Self-host entries are the GPU-host PoC models, each
# served by its own vLLM process on the model host (Option A). Final list is a
# PMC vote per the proposal.
CATALOG: List[CatalogModel] = [
    # --- self-hosted via per-model vLLM servers (g6e.xlarge, L40S 48GB) ---
    CatalogModel(
        id="self-host/gemma4-26b",
        display_name="Gemma 4 26B-A4B (self-hosted, multimodal)",
        provider="self-host",
        # Bare name, NOT "selfhost/gemma4-26b". render_litellm_config.py emits
        # this as the proxy's model_name, and litellm_client.py sends it as
        # {"model": ...}. gofannon builds "openai/gemma4-26b" and the litellm
        # SDK strips the provider prefix client-side, so the proxy receives
        # "gemma4-26b" -- a "selfhost/" prefix here makes every gofannon call
        # 400 on an unknown model. backend == served_name is the invariant.
        backend="gemma4-26b",
        context_window=131072,
        license="Apache-2.0",
        openness="open-weight",
        # Served OFF-HOST as the BF16 checkpoint, not the FP8 one that ran on
        # the local L40S. This field is governance metadata surfaced by
        # public(); naming the wrong checkpoint and precision is exactly the
        # silent gap provenance_record exists to prevent.
        weights_distribution="google/gemma-4-26B-A4B-it (HF, BF16) \u00b7 vLLM",
        training_data_provenance="undisclosed (Google DeepMind)",
        provenance_record="absent",
        self_hosted=True,
        modality="text+vision",
        served_name="gemma4-26b",
        api_base_env="LLMAO_SELFHOST_GEMMA_URL",
        supports_thinking=True,
        thinks_by_default=False,   # --reasoning-parser gemma4 leaves it off
        notes="MoE, ~4B active. General/multimodal/agentic default. "
              "Served off-host at BF16 on an 80GB card (~49GB weights, "
              "131072 window, ~856k-token KV cache). Measured ~100 tok/s "
              "single-stream sustained, ~492 tok/s aggregate at concurrency "
              "8. tau2-bench 85.5, LiveCodeBench v6 77.1 (vendor).",
    ),
    CatalogModel(
        id="self-host/qwen3-8b",
        display_name="Qwen3 8B (self-hosted, fast)",
        provider="self-host",
        # Bare name -- see the note on gemma4-26b above. backend ==
        # served_name is the invariant that keeps the proxy config, the
        # portal, and gofannon all agreeing.
        backend="qwen3-8b",
        # 40960, not the 8192 this entry carried while Qwen shared the card
        # with Gemma. That was a CO-RESIDENCY number. Gemma is now served
        # off-host, so Qwen has the whole L40S and takes the full
        # architectural window. If Gemma ever comes back onto this card,
        # BOTH models' windows have to be re-derived.
        context_window=40960,
        license="Apache-2.0",
        openness="open-weight",
        weights_distribution="Qwen/Qwen3-8B-FP8 (HF) \u00b7 vLLM",
        training_data_provenance="undisclosed (Alibaba)",
        provenance_record="absent",
        self_hosted=True,
        served_name="qwen3-8b",
        api_base_env="LLMAO_SELFHOST_QWEN8B_URL",
        supports_thinking=True,
        thinks_by_default=True,    # reasons unless enable_thinking=false
        notes="Fast lightweight tier for routine/cheap calls. Sole resident "
              "on the local L40S at FP8 (~8GB weights). Reasoning model: "
              "vLLM runs --reasoning-parser qwen3, and unlike Gemma the "
              "enable_thinking chat-template kwarg is safe to send.",
    ),

]

_BY_ID = {m.id: m for m in CATALOG}


def all_models() -> List[Dict]:
    return [m.public() for m in CATALOG]


def get(model_id: str) -> Optional[CatalogModel]:
    return _BY_ID.get(model_id)


def exists(model_id: str) -> bool:
    return model_id in _BY_ID