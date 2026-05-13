"""LLM provider abstraction and selection.

Each provider module under ``agent.providers`` owns its own SDK, env vars,
defaults, and error mapping. The rest of the agent only sees the
``Provider`` interface and the ``build_provider`` factory.
"""

from __future__ import annotations

import os
from typing import Literal

from agent.providers.base import Provider

ProviderName = Literal["anthropic", "openai"]


def resolved_llm_provider() -> ProviderName:
    """Return which LLM backend to use from ``MINI_AGENT_PROVIDER``.

    Returns:
        ``"anthropic"`` (default) or ``"openai"``.

    Raises:
        SystemExit: If the environment value is not a supported provider.
    """
    raw = os.getenv("MINI_AGENT_PROVIDER", "anthropic").strip().lower()
    if raw in ("", "anthropic"):
        return "anthropic"
    if raw == "openai":
        return "openai"
    raise SystemExit(
        f'Unsupported MINI_AGENT_PROVIDER={raw!r}. Use "anthropic" or "openai".'
    )


def build_provider(name: ProviderName) -> Provider:
    """Construct and configure the requested provider.

    The vendor-specific SDK is imported lazily so that the unused backend
    never touches the import path.

    Args:
        name: Provider id returned by :func:`resolved_llm_provider`.

    Returns:
        A ready-to-use ``Provider`` instance.
    """
    if name == "anthropic":
        from agent.providers.anthropic import AnthropicProvider

        return AnthropicProvider.setup()
    if name == "openai":
        from agent.providers.openai import OpenAIProvider

        return OpenAIProvider.setup()
    raise SystemExit(f"Unsupported provider: {name!r}.")


__all__ = ["Provider", "ProviderName", "build_provider", "resolved_llm_provider"]
