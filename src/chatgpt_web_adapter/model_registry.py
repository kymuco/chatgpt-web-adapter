from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

DEFAULT_MODEL = "gpt-5-3-mini"
DEFAULT_THINKING_MODEL = "gpt-5-6-thinking"


@dataclass(frozen=True)
class ModelCapability:
    """Evidence-backed convenience policy for one known ChatGPT web model slug.

    The registry is advisory policy, not a detector whitelist. Unknown explicit
    model slugs must remain pass-through so newly rolled out web models can still
    be observed before the registry is updated.
    """

    slug: str
    family: str
    ui_name: str
    reasoning_modes: Mapping[str, str]
    evidence: str


_GPT56_REASONING_MODES = MappingProxyType(
    {
        "medium": "standard",
        "high": "extended",
    }
)

MODEL_CAPABILITIES: Mapping[str, ModelCapability] = MappingProxyType(
    {
        DEFAULT_THINKING_MODEL: ModelCapability(
            slug=DEFAULT_THINKING_MODEL,
            family="gpt-5.6",
            ui_name="GPT-5.6 Sol",
            reasoning_modes=_GPT56_REASONING_MODES,
            evidence="live-attach-2026-08-07",
        ),
    }
)

MODEL_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "instant": DEFAULT_MODEL,
        "thinking": DEFAULT_THINKING_MODEL,
        "gpt-5.6": DEFAULT_THINKING_MODEL,
        "gpt-5.1": "gpt-5-1",
        "gpt-4.1": "gpt-4.1",
        "gpt-4.1-mini": "gpt-4.1-mini",
        "gpt-4.5": "gpt-4.5",
    }
)

REASONING_ALIASES: Mapping[str, str | None] = MappingProxyType(
    {
        "": None,
        "off": None,
        "none": None,
        "-": None,
        "instant": None,
        "medium": "standard",
        "high": "extended",
        "standard": "standard",
        "extended": "extended",
    }
)


def normalize_reasoning_effort(reasoning_effort: str | None) -> str | None:
    normalized = reasoning_effort.strip().lower() if isinstance(reasoning_effort, str) else None
    if normalized is None:
        return None
    if normalized not in REASONING_ALIASES:
        raise ValueError(
            "reasoning_effort must be one of: instant, medium, high, standard, extended, off/none/-"
        )
    return REASONING_ALIASES[normalized]


def resolve_model(model: str | None, reasoning_effort: str | None) -> str:
    """Resolve public convenience input without rejecting unknown explicit slugs."""

    if isinstance(model, str):
        model_name = model.strip()
        if not model_name:
            raise ValueError("model must not be empty")
        return MODEL_ALIASES.get(model_name.lower(), model_name)

    normalized_effort = normalize_reasoning_effort(reasoning_effort)
    if normalized_effort is not None:
        return DEFAULT_THINKING_MODEL
    return DEFAULT_MODEL


def get_model_capability(model: str) -> ModelCapability | None:
    if not isinstance(model, str):
        return None
    model_name = model.strip()
    if not model_name:
        return None
    resolved = MODEL_ALIASES.get(model_name.lower(), model_name)
    return MODEL_CAPABILITIES.get(resolved)
