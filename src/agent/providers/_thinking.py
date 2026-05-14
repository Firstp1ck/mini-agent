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
from typing import Literal

from agent.providers._shared import env_file_path, write_env_value

ThinkingLevel = Literal["off", "low", "medium", "high", "max", "xhigh"]

VALID_LEVELS: tuple[ThinkingLevel, ...] = (
    "off",
    "low",
    "medium",
    "high",
    "max",
    "xhigh",
)

# Per-model thinking-mode classification. Sources (verified Nov 2025):
# - https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking
# - https://platform.claude.com/docs/en/build-with-claude/effort
# - https://platform.claude.com/docs/en/about-claude/models/extended-thinking-models
# - https://developers.openai.com/docs/guides/reasoning
#
# Anthropic modes:
#  * ``adaptive_xhigh`` - adaptive thinking accepted, plus the ``xhigh`` effort
#    tier (Opus 4.7 only; manual ``type:"enabled"`` is rejected).
#  * ``adaptive``        - adaptive thinking accepted, effort up to ``max``
#    (Opus 4.6, Sonnet 4.6, Mythos Preview).
#  * ``manual``          - manual extended thinking via
#    ``type:"enabled" + budget_tokens``; the level dropdown maps to a budget
#    (Sonnet 4.5, Haiku 4.5, Opus 4.5 and older Claude 3.x models).
#  * ``none``            - never matched for Claude (every current Claude
#    accepts at least manual thinking); kept for the unknown-id fallback.
_ANTHROPIC_ADAPTIVE_XHIGH_PREFIXES: tuple[str, ...] = (
    "claude-opus-4-7",
)
_ANTHROPIC_ADAPTIVE_PREFIXES: tuple[str, ...] = (
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-mythos",
)

# OpenAI reasoning-capable model id prefixes. GPT-4 / gpt-3.5 / chatgpt-* are
# chat models and reject the ``reasoning`` parameter, so they only show
# ``auto`` / ``off`` in the picker.
_OPENAI_REASONING_PREFIXES: tuple[str, ...] = (
    "gpt-5",
    "o1",
    "o3",
    "o4",
    "o5",
)

# Values offered on first-run setup (saved to ``MINI_AGENT_THINKING``).
SETUP_THINKING_MENU: list[tuple[str, str]] = [
    ("auto", "API default (recommended)"),
    ("off", "Off — no extended thinking / minimal reasoning"),
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("max", "Max — deepest effort on supported Claude / xhigh on GPT"),
    ("xhigh", "xHigh — Claude Opus 4.7 / GPT-5 family only"),
]


def anthropic_thinking_mode(model_id: str) -> str:
    """Classify the thinking shape this Claude model accepts.

    Args:
        model_id: Anthropic model identifier (for example
            ``"claude-haiku-4-5"`` or ``"claude-opus-4-7-20251015"``).

    Returns:
        One of ``"adaptive_xhigh"``, ``"adaptive"``, ``"manual"``, or
        ``"none"`` (defensive default for unknown ids; treat as manual).
    """
    if any(model_id.startswith(p) for p in _ANTHROPIC_ADAPTIVE_XHIGH_PREFIXES):
        return "adaptive_xhigh"
    if any(model_id.startswith(p) for p in _ANTHROPIC_ADAPTIVE_PREFIXES):
        return "adaptive"
    if model_id.startswith("claude-"):
        return "manual"
    return "none"


def is_openai_reasoning_model(model_id: str) -> bool:
    """Return whether ``model_id`` accepts the ``reasoning`` request parameter.

    Args:
        model_id: OpenAI model identifier.

    Returns:
        ``True`` for GPT-5 family and o-series reasoning models, ``False`` for
        chat models like ``gpt-4o`` / ``gpt-4*`` / ``chatgpt-*`` / ``gpt-3.5*``.
    """
    return any(model_id.startswith(p) for p in _OPENAI_REASONING_PREFIXES)


def available_thinking_levels(provider_id: str, model_id: str) -> list[str]:
    """Return the ``SETUP_THINKING_MENU`` values supported by this model.

    The result always starts with ``"auto"`` and ``"off"``; provider/model
    specific effort levels are appended in menu order. Unknown providers fall
    through to the full effort set so the user can still try a value (the
    API will reject anything the model truly does not support).

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
        mode = anthropic_thinking_mode(model_id)
        if mode == "adaptive_xhigh":
            return base + extras_full
        if mode == "adaptive":
            return base + extras_no_xhigh
        if mode == "manual":
            return base + extras_no_xhigh
        return base

    if pid == "openai":
        if is_openai_reasoning_model(model_id):
            return base + extras_full
        return base

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
        ``True`` if ``thinking={"type": "adaptive"}`` is valid for this model
        (Opus 4.7, Opus 4.6, Sonnet 4.6, Mythos Preview).
    """
    return anthropic_thinking_mode(model_id) in {"adaptive", "adaptive_xhigh"}


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
    env_path = env_file_path()
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
    env_path = env_file_path()
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
    "anthropic_thinking_mode",
    "available_thinking_levels",
    "filter_thinking_menu",
    "is_openai_reasoning_model",
    "model_supports_adaptive_thinking",
    "prompt_thinking_level_cli",
    "resolved_thinking_level",
    "save_mini_agent_thinking",
    "thinking_env_needs_prompt",
]
