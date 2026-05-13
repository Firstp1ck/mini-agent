"""Provider resolution and initial conversation state for the GUI session."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import tkinter as tk
from tkinter import messagebox, ttk

from agent.prompt import (
    collect_guide_paths_walking_up,
    format_new_guide_sections,
    system_prompt,
)
from agent.providers import AVAILABLE_PROVIDERS, Provider, ProviderName, build_provider
from agent.providers._shared import write_env_value


def resolve_provider_name(root: tk.Tk) -> ProviderName | None:
    """Return a valid ``MINI_AGENT_PROVIDER`` value, prompting in Tk if unset.

    Args:
        root: Root window used as the dialog parent.

    Returns:
        Provider id, or ``None`` if the environment is invalid or the user
        cancels the picker.
    """
    raw = os.getenv("MINI_AGENT_PROVIDER", "").strip().lower()
    known = {name for name, _ in AVAILABLE_PROVIDERS}
    if raw in known:
        return cast(ProviderName, raw)
    if raw:
        messagebox.showerror(
            "mini-agent",
            f"Unsupported MINI_AGENT_PROVIDER={raw!r}. Fix .env or unset it to choose again.",
            parent=root,
        )
        return None

    choice = tk.StringVar(value=AVAILABLE_PROVIDERS[0][0])
    result: list[ProviderName | None] = [None]

    dialog = tk.Toplevel(root)
    dialog.title("Choose LLM provider")
    dialog.transient(root)
    dialog.grab_set()
    ttk.Label(dialog, text="Pick a provider (saved to .env):").pack(anchor="w", padx=12, pady=(12, 4))
    for name, label in AVAILABLE_PROVIDERS:
        ttk.Radiobutton(dialog, text=label, value=name, variable=choice).pack(anchor="w", padx=24)

    def on_ok() -> None:
        result[0] = cast(ProviderName, choice.get())
        dialog.destroy()

    def on_cancel() -> None:
        result[0] = None
        dialog.destroy()

    buttons = ttk.Frame(dialog)
    buttons.pack(pady=12)
    ttk.Button(buttons, text="OK", command=on_ok).pack(side="left", padx=4)
    ttk.Button(buttons, text="Cancel", command=on_cancel).pack(side="left", padx=4)
    root.wait_window(dialog)
    if result[0] is None:
        return None

    env_path = Path.cwd() / ".env"
    write_env_value(env_path, "MINI_AGENT_PROVIDER", result[0])
    os.environ["MINI_AGENT_PROVIDER"] = result[0]
    return result[0]


def start_session(provider_name: ProviderName) -> tuple[list[dict[str, str]], Provider, set[str]]:
    """Build provider and initial conversation state (same base as the CLI).

    Args:
        provider_name: Resolved provider id.

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
    return (
        f"Working directory: {cwd}\n"
        f"Provider: {provider.name} — model: {provider.model}\n"
        "Type a message below; assistant replies support Markdown "
        "(headings, lists, links, code fences, emphasis).\n"
    )
