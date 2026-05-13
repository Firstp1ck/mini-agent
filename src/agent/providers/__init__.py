"""LLM provider abstraction and selection.

Each provider module under ``agent.providers`` owns its own SDK, env vars,
defaults, and error mapping. The rest of the agent only sees the
``Provider`` interface and the ``build_provider`` factory.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, cast

from agent.providers._shared import write_env_value
from agent.providers.base import Provider

ProviderName = Literal["anthropic", "openai"]

AVAILABLE_PROVIDERS: list[tuple[ProviderName, str]] = [
    ("anthropic", "Anthropic (Claude)"),
    ("openai", "OpenAI (GPT)"),
]


def resolved_llm_provider() -> ProviderName:
    """Return which LLM backend to use, prompting once if no choice is stored.

    Order of resolution:

    1. If ``MINI_AGENT_PROVIDER`` is set to a known provider id, use it.
    2. If it is set to an unknown value, fail with a clear error.
    3. Otherwise prompt the user to pick from :data:`AVAILABLE_PROVIDERS`,
       persist the choice to ``.env`` as ``MINI_AGENT_PROVIDER``, and return it.

    Returns:
        Validated provider id.

    Raises:
        SystemExit: If the environment value is not a supported provider, or
            if the interactive prompt is cancelled without a selection.
    """
    raw = os.getenv("MINI_AGENT_PROVIDER", "").strip().lower()
    known = {name for name, _ in AVAILABLE_PROVIDERS}
    if raw in known:
        return cast(ProviderName, raw)
    if raw:
        ids = ", ".join(repr(name) for name, _ in AVAILABLE_PROVIDERS)
        raise SystemExit(f"Unsupported MINI_AGENT_PROVIDER={raw!r}. Use one of: {ids}.")
    return _prompt_for_provider()


def _prompt_for_provider() -> ProviderName:
    """Prompt the user to pick an LLM provider and save the choice to ``.env``.

    Returns:
        Selected provider id.

    Raises:
        SystemExit: If the prompt is cancelled without a selection.
    """
    env_path = Path.cwd() / ".env"

    print("\nChoose an LLM provider:")
    for index, (_, label) in enumerate(AVAILABLE_PROVIDERS, start=1):
        default_marker = " [default]" if index == 1 else ""
        print(f"  {index}. {label}{default_marker}")

    chosen: ProviderName | None = None
    while chosen is None:
        try:
            choice = input("Provider [default 1]: ").strip().lower()
        except (EOFError, KeyboardInterrupt) as exc:
            raise SystemExit("No provider selected. Exiting.") from exc

        if not choice:
            chosen = AVAILABLE_PROVIDERS[0][0]
        elif choice.isdigit() and 1 <= int(choice) <= len(AVAILABLE_PROVIDERS):
            chosen = AVAILABLE_PROVIDERS[int(choice) - 1][0]
        else:
            chosen = next((name for name, _ in AVAILABLE_PROVIDERS if name == choice), None)
            if chosen is None:
                print("Enter a number from the list, a provider name, or press Enter for the default.")

    write_env_value(env_path, "MINI_AGENT_PROVIDER", chosen)
    os.environ["MINI_AGENT_PROVIDER"] = chosen
    print(f"Saved MINI_AGENT_PROVIDER={chosen} to {env_path}.")
    return chosen


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


__all__ = [
    "AVAILABLE_PROVIDERS",
    "Provider",
    "ProviderName",
    "build_provider",
    "resolved_llm_provider",
]
