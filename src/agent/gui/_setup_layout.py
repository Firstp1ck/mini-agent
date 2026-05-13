"""Static layout and value helpers for the unified GUI setup dialog.

Split out of :mod:`agent.gui.setup_dialog` so the dialog file stays under
the 600-line cap and keeps its focus on the controller lifecycle. Nothing
in this module touches global state — every function is a pure helper that
returns widgets or formatted strings for the controller to drive.
"""

from __future__ import annotations

import os
from typing import Any

import tkinter as tk

from agent.gui._setup_providers import ProviderSetupInfo
from agent.gui._setup_style import (
    SHELL_BG,
    apply_setup_style,
    make_card,
    make_field_combo,
    make_field_entry,
    make_field_label,
    make_primary_button,
    make_secondary_button,
    make_status_label,
)
from agent.gui.fonts import ui_font
from agent.gui.theme import MUTED
from agent.providers import AVAILABLE_PROVIDERS, ProviderName
from agent.providers._thinking import SETUP_THINKING_MENU, filter_thinking_menu


def build_setup_widgets(dialog: tk.Toplevel) -> dict[str, Any]:
    """Lay out the dialog widgets and return a handle dict.

    The API key row (label + entry + Verify button) and the hint label are
    created but not gridded; the caller's provider-change handler grids them
    once a provider is picked.

    Args:
        dialog: Toplevel that will host the form.

    Returns:
        Mapping of widget/variable names to instances. Keys: ``provider_var``,
        ``provider_combo``, ``api_label``, ``api_row``, ``api_entry``,
        ``api_var``, ``verify_btn``, ``verify_indicator``,
        ``verify_status_var``, ``api_hint``, ``model_var``, ``model_combo``,
        ``thinking_var``, ``thinking_combo``, ``status_var``, ``ok_btn``,
        ``cancel_btn``.
    """
    apply_setup_style(dialog)
    dialog.configure(bg=SHELL_BG)

    outer = tk.Frame(dialog, bg=SHELL_BG, padx=18, pady=18)
    outer.pack(fill="both", expand=True)
    card = make_card(outer)
    card.pack(fill="both", expand=True, ipadx=18, ipady=18)

    provider_var = tk.StringVar()
    model_var = tk.StringVar()
    api_var = tk.StringVar()
    thinking_var = tk.StringVar()
    status_var = tk.StringVar(value="")

    make_field_label(card, "Provider:").grid(row=0, column=0, sticky="w", pady=6, padx=(16, 12))
    provider_combo = make_field_combo(card, provider_var)
    provider_combo.configure(values=[label for _, label in AVAILABLE_PROVIDERS], state="readonly")
    provider_combo.grid(row=0, column=1, sticky="ew", pady=6, padx=(0, 16))

    make_field_label(card, "Model:").grid(row=1, column=0, sticky="w", pady=6, padx=(16, 12))
    model_combo = make_field_combo(card, model_var)
    model_combo.grid(row=1, column=1, sticky="ew", pady=6, padx=(0, 16))

    make_field_label(card, "Thinking:").grid(row=2, column=0, sticky="w", pady=6, padx=(16, 12))
    thinking_combo = make_field_combo(card, thinking_var)
    thinking_combo.grid(row=2, column=1, sticky="ew", pady=6, padx=(0, 16))

    api_label = make_field_label(card, "API key:")
    api_row = tk.Frame(card, bg=card["bg"])
    api_entry = make_field_entry(api_row, api_var, show="•")
    verify_status_var = tk.StringVar(value="")
    verify_indicator = tk.Label(
        api_row,
        textvariable=verify_status_var,
        bg=card["bg"],
        fg=MUTED,
        font=ui_font(13, bold=True),
        width=2,
        anchor="center",
    )
    verify_btn = make_secondary_button(api_row, "Verify")
    api_entry.pack(side="left", fill="x", expand=True, ipady=6)
    verify_btn.pack(side="right", padx=(8, 0))
    verify_indicator.pack(side="right")
    api_row.columnconfigure(0, weight=1)

    api_hint = tk.Label(
        card,
        text="Enter your API key and click Verify to load every model available to your account.",
        bg=card["bg"],
        fg=MUTED,
        font=ui_font(9),
        anchor="w",
        justify="left",
        wraplength=420,
    )

    status_label = make_status_label(card, status_var)
    status_label.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(12, 0), padx=16)

    button_row = tk.Frame(card, bg=card["bg"])
    button_row.grid(row=6, column=0, columnspan=2, pady=(16, 0), padx=16, sticky="e")
    ok_btn = make_primary_button(button_row, "OK")
    cancel_btn = make_secondary_button(button_row, "Cancel")
    cancel_btn.pack(side="right", padx=(8, 0))
    ok_btn.pack(side="right")

    return {
        "card": card,
        "provider_var": provider_var,
        "provider_combo": provider_combo,
        "api_label": api_label,
        "api_row": api_row,
        "api_entry": api_entry,
        "api_var": api_var,
        "verify_btn": verify_btn,
        "verify_indicator": verify_indicator,
        "verify_status_var": verify_status_var,
        "api_hint": api_hint,
        "model_var": model_var,
        "model_combo": model_combo,
        "thinking_var": thinking_var,
        "thinking_combo": thinking_combo,
        "status_var": status_var,
        "ok_btn": ok_btn,
        "cancel_btn": cancel_btn,
    }


def thinking_menu_for(provider_id: ProviderName, model_id: str) -> list[tuple[str, str]]:
    """Return the thinking menu filtered to what this provider+model accepts.

    Falls back to the full :data:`SETUP_THINKING_MENU` if the filter returns
    nothing (defensive — should never happen in practice).

    Args:
        provider_id: Resolved provider id.
        model_id: Selected model id (may be empty if the user hasn't chosen).

    Returns:
        Ordered ``(value, label)`` pairs for the dropdown.
    """
    if not model_id:
        return list(SETUP_THINKING_MENU)
    menu = filter_thinking_menu(provider_id, model_id)
    return menu or list(SETUP_THINKING_MENU)


def thinking_display_entry(menu: list[tuple[str, str]], value: str) -> str:
    """Return the combobox display string for ``value``, or pick the default.

    The display is just the bare level name (for example ``"auto"`` or
    ``"medium"``) so the dropdown stays scannable.

    Args:
        menu: Available ``(value, label)`` entries from :func:`thinking_menu_for`.
        value: Preferred value (typically from ``MINI_AGENT_THINKING``).

    Returns:
        ``value`` when it appears in ``menu``; otherwise the first menu entry's
        value.
    """
    for v, _label in menu:
        if v == value:
            return v
    return menu[0][0]


def model_dropdown_values(info: ProviderSetupInfo) -> list[str]:
    """Return the fallback model ids as combobox entries.

    The display string is the bare model identifier (for example
    ``"gpt-5.5"``). Providers like OpenAI use the same string for id and
    display name, so an ``"id — name"`` form just duplicated the text.

    Args:
        info: Provider setup metadata.

    Returns:
        Ordered model id strings for the chosen provider.
    """
    return [mid for mid, _ in info.fallback_models]


def select_initial_model(info: ProviderSetupInfo, values: list[str]) -> str:
    """Pick the model entry that matches env or the provider's default.

    Args:
        info: Provider setup metadata.
        values: ``model_dropdown_values`` for the provider.

    Returns:
        The combobox display string to preselect, or ``""`` if the fallback
        list is empty.
    """
    stored = os.getenv(info.model_env, "").strip() or info.default_model
    if stored in values:
        return stored
    return values[0] if values else ""


__all__ = [
    "build_setup_widgets",
    "model_dropdown_values",
    "select_initial_model",
    "thinking_display_entry",
    "thinking_menu_for",
]
