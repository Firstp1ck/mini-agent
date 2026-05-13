"""Provider build and initial conversation state for the GUI session.

All interactive setup (provider id, API key, model id, thinking level) now
goes through :mod:`agent.gui.setup_dialog`. By the time :func:`start_session`
runs, every required env var is already in place, so this module only has to
build the provider client and seed the conversation.
"""

from __future__ import annotations

import os
from pathlib import Path

from agent.prompt import (
    collect_guide_paths_walking_up,
    format_new_guide_sections,
    system_prompt,
)
from agent.providers import Provider, ProviderName, build_provider


def start_session(provider_name: ProviderName) -> tuple[list[dict[str, str]], Provider, set[str]]:
    """Build the provider client and seed the initial conversation.

    Args:
        provider_name: Resolved provider id (already present in
            ``MINI_AGENT_PROVIDER`` after the setup dialog).

    Returns:
        Tuple of ``(conversation, provider, injected_guide_paths)``.
    """
    provider = build_provider(provider_name)
    injected_guide_paths: set[str] = set()
    initial_suffix, _ = format_new_guide_sections(
        collect_guide_paths_walking_up(Path.cwd()), injected_guide_paths
    )
    conversation: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt() + initial_suffix}
    ]
    return conversation, provider, injected_guide_paths


def session_header_text(cwd: Path, provider: Provider) -> str:
    """Build the multi-line intro banner shown when the GUI session is ready.

    Args:
        cwd: Current working directory shown to the user.
        provider: Active provider (name and model label).

    Returns:
        Plain text for the transcript system banner.
    """
    thinking = os.getenv("MINI_AGENT_THINKING", "").strip() or "auto"
    return (
        f"Working directory: {cwd}\n"
        f"Provider: {provider.name} — model: {provider.model}\n"
        f"Thinking level: {thinking}\n"
        "Type a message below; assistant replies support Markdown "
        "(headings, lists, links, code fences, emphasis).\n"
    )
