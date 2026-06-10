"""Hayward model catalog.

Phase 1 keeps the catalog as a small in-code registry. Each entry carries the
metadata the Hayward proposal requires that ordinary model cards omit:
licensing, openness, weights distribution, and training-data provenance — with
``provenance_record`` made explicit so an absent record is a field, not a
silent gap. In Phase 4 these fields get sourced from Apache Lineage; for now
they are hand-curated.

The catalog is the single source of truth the portal lists and the litellm
proxy config is generated from (see scripts/render_litellm_config.py).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class CatalogModel:
    # Stable id callers pass as "model" in a chat request. Matches the
    # model_name registered in the litellm proxy config.
    id: str
    display_name: str
    provider: str                 # external provider or "self-host"
    backend: str                  # litellm model string / route target
    context_window: int

    # --- proposal-required governance metadata ---------------------------
    license: str                  # weights license, e.g. "Apache-2.0", "Llama-3-Community", "proprietary"
    openness: str                 # "open-weight" | "open-source" | "proprietary"
    weights_distribution: str     # where weights live, or "n/a (API only)"
    training_data_provenance: str # short note, or "undisclosed"
    provenance_record: str        # "present" | "absent" — explicit, never silent

    self_hosted: bool = False
    notes: Optional[str] = None

    def public(self) -> Dict:
        return asdict(self)


# Phase 1 seed catalog. Final list is a PMC vote per the proposal; this is a
# defensible starting set spanning open-weight self-host + external APIs.
CATALOG: List[CatalogModel] = [
    CatalogModel(
        id="self-host/llama-3.1-8b",
        display_name="Llama 3.1 8B (self-hosted)",
        provider="self-host",
        backend="openai/llama-3.1-8b-instruct",   # vast.ai vLLM, OpenAI-compatible
        context_window=131072,
        license="Llama-3.1-Community",
        openness="open-weight",
        weights_distribution="meta-llama/Llama-3.1-8B-Instruct (HF)",
        training_data_provenance="undisclosed (Meta)",
        provenance_record="absent",
        self_hosted=True,
        notes="Runs on the ASF/vast.ai self-host endpoint. Default target for sensitive content in Phase 3.",
    ),
    CatalogModel(
        id="self-host/mistral-7b",
        display_name="Mistral 7B Instruct (self-hosted)",
        provider="self-host",
        backend="openai/mistral-7b-instruct",
        context_window=32768,
        license="Apache-2.0",
        openness="open-weight",
        weights_distribution="mistralai/Mistral-7B-Instruct-v0.3 (HF)",
        training_data_provenance="undisclosed (Mistral)",
        provenance_record="absent",
        self_hosted=True,
        notes="Apache-2.0 weights; the cleanest licensing story in the seed set.",
    ),
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
