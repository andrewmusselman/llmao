"""Hayward model catalog.

Phase 1 keeps the catalog as a small in-code registry. Each entry carries the
metadata the Hayward proposal requires that ordinary model cards omit:
licensing, openness, weights distribution, and training-data provenance — with
``provenance_record`` made explicit so an absent record is a field, not a
silent gap. In Phase 4 these fields get sourced from Apache Lineage; for now
they are hand-curated.

The self-host entries below map to local Ollama models via the litellm proxy
(see litellm/config.yaml). The ``backend`` string of each entry MUST equal a
``model_name`` in that config.
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

    def public(self) -> Dict:
        return asdict(self)


# Phase 1 seed catalog, self-host entries pinned to current Apache-2.0 Ollama
# models. Final list is a PMC vote per the proposal.
CATALOG: List[CatalogModel] = [
    # --- self-hosted via local Ollama (matches `ollama list` on a 6GB GPU) ---
    CatalogModel(
        id="self-host/qwen2.5-coder-7b",
        display_name="Qwen2.5-Coder 7B (self-hosted)",
        provider="self-host",
        backend="selfhost/qwen2.5-coder-7b",
        context_window=32768,
        license="Apache-2.0",
        openness="open-weight",
        weights_distribution="Qwen/Qwen2.5-Coder-7B (HF) \u00b7 ollama qwen2.5-coder:7b",
        training_data_provenance="undisclosed (Alibaba)",
        provenance_record="absent",
        self_hosted=True,
        notes="~4.7GB. Best local code model that fits a 6GB GPU: writing, explaining, debugging, review.",
    ),
    CatalogModel(
        id="self-host/qwen3.5-4b",
        display_name="Qwen3.5 4B (self-hosted)",
        provider="self-host",
        backend="selfhost/qwen3.5-4b",
        context_window=131072,
        license="Apache-2.0",
        openness="open-weight",
        weights_distribution="Qwen/Qwen3.5-4B (HF) \u00b7 ollama qwen3.5:4b",
        training_data_provenance="undisclosed (Alibaba)",
        provenance_record="absent",
        self_hosted=True,
        notes="~3.4GB. Newest general/document workhorse: drafting, summarizing, Q&A. Fast on 6GB. Recommended default.",
    ),
    CatalogModel(
        id="self-host/gemma3-4b",
        display_name="Gemma 3 4B (self-hosted, multimodal)",
        provider="self-host",
        backend="selfhost/gemma3-4b",
        context_window=131072,
        license="Gemma",
        openness="open-weight",
        weights_distribution="google/gemma-3-4b (HF) \u00b7 ollama gemma3:4b",
        training_data_provenance="undisclosed (Google DeepMind)",
        provenance_record="absent",
        self_hosted=True,
        modality="text+vision",
        notes="~3.3GB. RAM-efficient, multimodal (text+image). Weak tool-calling. Portal upload is text-only in Phase 1.",
    ),
    CatalogModel(
        id="self-host/qwen3-8b",
        display_name="Qwen3 8B (self-hosted)",
        provider="self-host",
        backend="selfhost/qwen3-8b",
        context_window=131072,
        license="Apache-2.0",
        openness="open-weight",
        weights_distribution="Qwen/Qwen3-8B (HF) \u00b7 ollama qwen3:8b",
        training_data_provenance="undisclosed (Alibaba)",
        provenance_record="absent",
        self_hosted=True,
        notes="~5.2GB, at the 6GB edge (small CPU spill). Reasoning-capable step up; a bit slower than the 4B models.",
    ),
    CatalogModel(
        id="self-host/deepseek-r1-8b",
        display_name="DeepSeek-R1 8B distill (self-hosted, reasoning)",
        provider="self-host",
        backend="selfhost/deepseek-r1-8b",
        context_window=131072,
        license="MIT",
        openness="open-weight",
        weights_distribution="deepseek-ai/DeepSeek-R1-Distill (HF) \u00b7 ollama deepseek-r1:8b",
        training_data_provenance="distill of Llama/Qwen base on R1 reasoning traces",
        provenance_record="absent",
        self_hosted=True,
        notes="~5.2GB, at the 6GB edge. Reasoning model: emits visible <think> chain-of-thought before the answer. Slower (verbose). A distill, NOT the 671B R1.",
    ),

    # --- external providers ---------------------------------------------
    CatalogModel(
        id="openai/gpt-4o-mini",
        display_name="GPT-4o mini",
        provider="openai",
        backend="openai/gpt-4o-mini",
        context_window=128000,
        license="proprietary",
        openness="proprietary",
        weights_distribution="n/a (API only)",
        training_data_provenance="undisclosed (OpenAI)",
        provenance_record="absent",
        notes="External provider. Not eligible for sensitive content once Phase 2 scanning lands.",
    ),
    CatalogModel(
        id="anthropic/claude-haiku",
        display_name="Claude Haiku",
        provider="anthropic",
        backend="anthropic/claude-haiku-4-5",
        context_window=200000,
        license="proprietary",
        openness="proprietary",
        weights_distribution="n/a (API only)",
        training_data_provenance="undisclosed (Anthropic)",
        provenance_record="absent",
        notes="External provider.",
    ),
]

_BY_ID = {m.id: m for m in CATALOG}


def all_models() -> List[Dict]:
    return [m.public() for m in CATALOG]


def get(model_id: str) -> Optional[CatalogModel]:
    return _BY_ID.get(model_id)


def exists(model_id: str) -> bool:
    return model_id in _BY_ID