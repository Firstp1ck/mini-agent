"""Shared resolver for the user-facing thinking / reasoning knob.

One env var, ``MINI_AGENT_THINKING``, controls extended thinking on Anthropic
and reasoning effort on OpenAI. Each provider module translates the generic
level into its own request shape (Anthropic ``thinking`` + ``output_config``,
OpenAI ``reasoning``).

Defaults at the time of writing (always check the live provider docs):

- Anthropic: extended thinking is OFF on every API model except
  ``claude-mythos-preview`` (adaptive by default). When you opt in with
  ``thinking={"type": "adaptive"}``, the default effort is ``high``.
- OpenAI: reasoning models always reason. ``reasoning.effort`` defaults to
  ``medium`` on ``gpt-5.5``; other models may default differently.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from agent.providers._shared import write_env_value

ThinkingLevel = Literal["off", "low", "medium", "high", "max", "xhigh"]

VALID_LEVELS: tuple[ThinkingLevel, ...] = (
    "off",
    "low",
    "medium",
    "high",
    "max",
    "xhigh",
)

# Claude model ids that accept ``thinking={"type": "adaptive"}``. See
# https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking
_ADAPTIVE_CLAUDE_PREFIXES: tuple[str, ...] = (
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-mythos",
)

# Values offered on first-run setup (saved to ``MINI_AGENT_THINKING``).
SETUP_THINKING_MENU: list[tuple[str, str]] = [
    ("auto", "API default (recommended)"),
    ("off", "Off — no Claude extended thinking; minimal GPT reasoning"),
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("max", "Max — deepest adaptive effort on Claude; maps to xhigh on GPT"),
    ("xhigh", "xHigh — deepest reasoning on GPT where supported"),
]

# Per-model effort support (May 2026). See:
# - https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking
# - https://developers.openai.com/api/docs/guides/reasoning
#
# Claude Opus 4.7 is the only model that accepts ``xhigh``; Opus 4.6 / Sonnet
# 4.6 / Mythos accept the adaptive set without ``xhigh``. Older Claude models
# don't accept adaptive thinking at all (only ``auto`` and ``off`` mean
# anything for them).
_ANTHROPIC_OPUS_4_7_PREFIX = "claude-opus-4-7"
_ANTHROPIC_ADAPTIVE_NO_XHIGH_PREFIXES: tuple[str, ...] = (
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-mythos",
)

# GPT-5.4 and GPT-5.5 model pages confirm: none, low, medium, high, xhigh.
_OPENAI_FULL_EFFORT_PREFIXES: tuple[str, ...] = (
    "gpt-5.5",
    "gpt-5.4",
)


def available_thinking_levels(provider_id: str, model_id: str) -> list[str]:
    """Return the ``SETUP_THINKING_MENU`` values supported by this model.

    The result always starts with ``"auto"`` and ``"off"``; provider/model
    specific effort levels are appended in menu order. Unknown providers or
    models get the full set so the user can still try a value (the API will
    reject anything the model truly does not support).

    Args:
        provider_id: ``"anthropic"`` or ``"openai"`` (case-insensitive).
        model_id: Model identifier (for example ``"claude-sonnet-4-6"``).

    Returns:
        Ordered list of supported level keys, a subset of the first column of
        :data:`SETUP_THINKING_MENU`.
    """
    base: list[str] = ["auto", "off"]
    extras_full = ["low", "medium", "high", "max", "xhigh"]
    extras_no_xhigh = ["low", "medium", "high", "max"]

    pid = provider_id.strip().lower()
    if pid == "anthropic":
        if model_id.startswith(_ANTHROPIC_OPUS_4_7_PREFIX):
            return base + extras_full
        if any(model_id.startswith(prefix) for prefix in _ANTHROPIC_ADAPTIVE_NO_XHIGH_PREFIXES):
            return base + extras_no_xhigh
        return base

    if pid == "openai":
        if any(model_id.startswith(prefix) for prefix in _OPENAI_FULL_EFFORT_PREFIXES):
            return base + extras_full
        return base + extras_full

    return base + extras_full


def filter_thinking_menu(provider_id: str, model_id: str) -> list[tuple[str, str]]:
    """Return :data:`SETUP_THINKING_MENU` filtered to supported levels.

    Args:
        provider_id: ``"anthropic"`` or ``"openai"``.
        model_id: Model identifier.

    Returns:
        Subset of :data:`SETUP_THINKING_MENU` preserving the original order.
    """
    allowed = set(available_thinking_levels(provider_id, model_id))
    return [(value, label) for value, label in SETUP_THINKING_MENU if value in allowed]


def model_supports_adaptive_thinking(model_id: str) -> bool:
    """Return whether ``model_id`` accepts adaptive extended thinking on Claude.

    Args:
        model_id: Anthropic model identifier.

    Returns:
        ``True`` if ``thinking={"type": "adaptive"}`` is valid for this model.
    """
    return any(model_id.startswith(prefix) for prefix in _ADAPTIVE_CLAUDE_PREFIXES)


def thinking_env_needs_prompt() -> bool:
    """Return ``True`` when ``MINI_AGENT_THINKING`` is unset and setup should ask.

    A non-empty value (including ``auto``) means the user has already chosen
    or configured the variable; no interactive prompt is needed.

    Returns:
        Whether first-run onboarding should offer a thinking level.
    """
    return not os.getenv("MINI_AGENT_THINKING", "").strip()


def save_mini_agent_thinking(value: str) -> None:
    """Persist ``MINI_AGENT_THINKING`` to ``.env`` and the process environment.

    Args:
        value: Stored verbatim (for example ``"auto"`` or ``"medium"``).
    """
    env_path = Path.cwd() / ".env"
    write_env_value(env_path, "MINI_AGENT_THINKING", value)
    os.environ["MINI_AGENT_THINKING"] = value


def prompt_thinking_level_cli(provider_name: str, model_id: str) -> None:
    """Prompt once for ``MINI_AGENT_THINKING`` and save it when unset.

    The menu is filtered to the effort levels that the selected provider and
    model actually accept (see :func:`available_thinking_levels`).

    Args:
        provider_name: ``"anthropic"`` or ``"openai"`` (case-insensitive).
        model_id: Resolved model id shown next to the menu.

    Raises:
        SystemExit: If the prompt is cancelled without a selection.
    """
    if not thinking_env_needs_prompt():
        return

    menu = filter_thinking_menu(provider_name, model_id)
    print(f"\nChoose a thinking / reasoning level (model: {model_id}):")
    for index, (value, label) in enumerate(menu, start=1):
        default_marker = " [default]" if index == 1 else ""
        print(f"  {index}. {label} ({value}){default_marker}")

    if provider_name.lower() == "anthropic" and not model_supports_adaptive_thinking(model_id):
        print(
            "\nNote: This Claude model does not support adaptive extended thinking; "
            "only 'auto' and 'off' are offered."
        )

    default_index = 0
    env_path = Path.cwd() / ".env"
    while True:
        try:
            choice = input(f"Thinking level [default {default_index + 1}]: ").strip().lower()
        except (EOFError, KeyboardInterrupt) as exc:
            raise SystemExit("No thinking level selected. Exiting.") from exc

        if not choice:
            save_mini_agent_thinking(menu[default_index][0])
            print(f"Saved MINI_AGENT_THINKING={menu[default_index][0]} to {env_path}.")
            return
        if choice.isdigit() and 1 <= int(choice) <= len(menu):
            value = menu[int(choice) - 1][0]
            save_mini_agent_thinking(value)
            print(f"Saved MINI_AGENT_THINKING={value} to {env_path}.")
            return
        if any(choice == value for value, _ in menu):
            save_mini_agent_thinking(choice)
            print(f"Saved MINI_AGENT_THINKING={choice} to {env_path}.")
            return

        print("Enter a number from the list, a level name (e.g. auto, medium), or press Enter for the default.")


def resolved_thinking_level() -> ThinkingLevel | None:
    """Return the configured thinking level, or ``None`` for provider default.

    Reads ``MINI_AGENT_THINKING`` from the environment. An empty value or
    ``"auto"`` means: let each provider use whatever the underlying API would
    do by default (adaptive thinking for current Claude models, ``medium``
    reasoning effort for GPT-5 family models).

    Returns:
        Validated ``ThinkingLevel`` string, or ``None`` when no override is
        configured.

    Raises:
        SystemExit: If the env var is set to an unsupported value.
    """
    raw = os.getenv("MINI_AGENT_THINKING", "").strip().lower()
    if not raw or raw == "auto":
        return None
    if raw in VALID_LEVELS:
        return raw  # type: ignore[return-value]
    valid = ", ".join(repr(level) for level in VALID_LEVELS)
    raise SystemExit(
        f"Unsupported MINI_AGENT_THINKING={raw!r}. "
        f"Use 'off', 'auto', or one of: {valid}."
    )


__all__ = [
    "SETUP_THINKING_MENU",
    "ThinkingLevel",
    "VALID_LEVELS",
    "available_thinking_levels",
    "filter_thinking_menu",
    "model_supports_adaptive_thinking",
    "prompt_thinking_level_cli",
    "resolved_thinking_level",
    "save_mini_agent_thinking",
    "thinking_env_needs_prompt",
]
