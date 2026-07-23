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
        backend="selfhost/gemma4-26b",
        context_window=131072,
        license="Apache-2.0",
        openness="open-weight",
        weights_distribution="RedHatAI/gemma-4-26B-A4B-it-FP8-Dynamic (HF) \u00b7 vLLM",
        training_data_provenance="undisclosed (Google DeepMind)",
        provenance_record="absent",
        self_hosted=True,
        modality="text+vision",
        served_name="gemma4-26b",
        api_base_env="LLMAO_SELFHOST_GEMMA_URL",
        notes="MoE, ~4B active. General/multimodal/agentic default. "
              "Pre-quantized FP8 checkpoint (~28GB VRAM); requires vLLM "
              ">=0.19.1 and --enforce-eager. tau2-bench 85.5, LiveCodeBench "
              "v6 77.1 (vendor).",
    ),
    # --- ROTATION CANDIDATE (not currently resident) ---------------------
    # Qwen 3.6 27B coder was dropped from the resident set: one L40S (44 GiB
    # usable) cannot co-host Gemma-4-26B (~28GB) + a 27B coder + the 8B at
    # once, even at FP8. To offer it, either (a) run it via vLLM sleep-mode
    # rotation (few-second wake cost), or (b) provision a second GPU.
    # Confirmed available as a pre-quantized checkpoint that loads on our
    # engine: Qwen/Qwen3.6-27B-FP8 (HF), vLLM >=0.19.0. Re-add a CatalogModel
    # entry here when a rotation or larger-GPU story is in place.
    # --- NOT SERVED (2026-07-23) -----------------------------------------
    # Qwen3 8B was removed from the GPU: it was holding ~12GB of VRAM that
    # nothing used, and forcing Gemma to run --enforce-eager at gpu-util 0.68.
    # Gemma is now sole resident (0.90 util, 131072 context, CUDA graphs on).
    # To restore, uncomment this AND re-add the vllm-qwen8b docker::run block
    # in llmao.pp (plus the litellm require and LLMAO_SELFHOST_QWEN8B_URL env)
    # -- and re-derive both models' --max-model-len for co-residency, since
    # Gemma's current 131072 is a sole-resident number.
    # CatalogModel(
    #     id="self-host/qwen3-8b",
    #     display_name="Qwen3 8B (self-hosted, fast)",
    #     provider="self-host",
    #     backend="selfhost/qwen3-8b",
    #     context_window=8192,
    #     license="Apache-2.0",
    #     openness="open-weight",
    #     weights_distribution="Qwen/Qwen3-8B-FP8 (HF) \u00b7 vLLM",
    #     training_data_provenance="undisclosed (Alibaba)",
    #     provenance_record="absent",
    #     self_hosted=True,
    #     served_name="qwen3-8b",
    #     api_base_env="LLMAO_SELFHOST_QWEN8B_URL",
    #     notes="Fast lightweight tier for routine/cheap calls.",
    # ),

]

_BY_ID = {m.id: m for m in CATALOG}


def all_models() -> List[Dict]:
    return [m.public() for m in CATALOG]


def get(model_id: str) -> Optional[CatalogModel]:
    return _BY_ID.get(model_id)


def exists(model_id: str) -> bool:
    return model_id in _BY_ID