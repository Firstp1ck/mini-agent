"""Theme glue for the setup dialog: matches the chat shell's look.

Reuses :mod:`agent.gui.theme` colors and :func:`agent.gui.fonts.ui_font` so
the popup feels like a panel of the main app instead of a default Tk dialog.
"""

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

from agent.gui.fonts import ui_font
from agent.gui.theme import (
    ACCENT,
    ACCENT_ACTIVE,
    CHAT_FG,
    CHAT_SURFACE,
    COMPOSER_BG,
    DIVIDER,
    MUTED,
    SHELL_BG,
)

_INPUT_BG = "#ffffff"
_INPUT_BG_DISABLED = "#f1f5f9"
_INPUT_FG_DISABLED = "#94a3b8"


def apply_setup_style(dialog: tk.Toplevel) -> None:
    """Register the ``Setup.TCombobox`` style and listbox colors for ``dialog``.

    Safe to call more than once; ``ttk.Style`` configurations are global, and
    the listbox option_add lookups are scoped to the dialog instance.

    Args:
        dialog: Toplevel that will host setup widgets.
    """
    style = ttk.Style()
    style.configure(
        "Setup.TCombobox",
        fieldbackground=_INPUT_BG,
        background=_INPUT_BG,
        foreground=CHAT_FG,
        bordercolor=DIVIDER,
        lightcolor=DIVIDER,
        darkcolor=DIVIDER,
        arrowcolor=MUTED,
        borderwidth=1,
        padding=6,
    )
    style.map(
        "Setup.TCombobox",
        fieldbackground=[
            ("disabled", _INPUT_BG_DISABLED),
            ("readonly", _INPUT_BG),
        ],
        foreground=[("disabled", _INPUT_FG_DISABLED)],
        bordercolor=[("focus", ACCENT)],
        lightcolor=[("focus", ACCENT)],
        darkcolor=[("focus", ACCENT)],
    )
    dialog.option_add("*TCombobox*Listbox.background", _INPUT_BG)
    dialog.option_add("*TCombobox*Listbox.foreground", CHAT_FG)
    dialog.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    dialog.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    dialog.option_add("*TCombobox*Listbox.borderWidth", 0)


def make_card(parent: tk.Widget) -> tk.Frame:
    """Return the card-style inner frame used to host all form fields.

    Args:
        parent: Container that the card is packed into.

    Returns:
        A :class:`tk.Frame` with the chat-surface background and a thin
        divider border, ready to host grid-positioned children.
    """
    card = tk.Frame(
        parent,
        bg=CHAT_SURFACE,
        highlightthickness=1,
        highlightbackground=DIVIDER,
        bd=0,
    )
    card.grid_columnconfigure(1, weight=1)
    return card


def make_field_label(parent: tk.Widget, text: str) -> tk.Label:
    """Return a label styled for the setup card (left column of each row)."""
    return tk.Label(
        parent,
        text=text,
        bg=CHAT_SURFACE,
        fg=CHAT_FG,
        font=ui_font(11),
        anchor="w",
    )


def make_field_entry(parent: tk.Widget, var: tk.StringVar, *, show: str | None) -> tk.Entry:
    """Return an entry styled like the chat composer entry.

    Args:
        parent: Card frame.
        var: ``StringVar`` bound to the entry value.
        show: Optional masking character for password-style entries.

    Returns:
        Configured :class:`tk.Entry` with focus highlight in accent blue.
    """
    kwargs: dict[str, Any] = dict(
        textvariable=var,
        bd=0,
        relief=tk.FLAT,
        highlightthickness=2,
        highlightcolor=ACCENT,
        highlightbackground=DIVIDER,
        bg=_INPUT_BG,
        fg=CHAT_FG,
        insertbackground=CHAT_FG,
        font=ui_font(11),
        disabledbackground=_INPUT_BG_DISABLED,
        disabledforeground=_INPUT_FG_DISABLED,
    )
    if show:
        kwargs["show"] = show
    return tk.Entry(parent, **kwargs)


def make_field_combo(parent: tk.Widget, var: tk.StringVar) -> ttk.Combobox:
    """Return a readonly combobox using the ``Setup.TCombobox`` style.

    Args:
        parent: Card frame.
        var: ``StringVar`` bound to the selected value.

    Returns:
        Combobox initially in ``disabled`` state until the caller seeds it.
    """
    return ttk.Combobox(
        parent,
        textvariable=var,
        values=[],
        state="disabled",
        style="Setup.TCombobox",
        font=ui_font(11),
        width=36,
    )


def make_status_label(parent: tk.Widget, var: tk.StringVar) -> tk.Label:
    """Return the muted status line shown at the bottom of the card."""
    return tk.Label(
        parent,
        textvariable=var,
        bg=CHAT_SURFACE,
        fg=MUTED,
        font=ui_font(9),
        anchor="w",
        justify="left",
        wraplength=420,
    )


def make_primary_button(parent: tk.Widget, text: str) -> tk.Button:
    """Return an accent-colored button that mimics the chat Send button.

    Hover transitions to ``ACCENT_ACTIVE`` while the button is enabled.
    """
    btn = tk.Button(
        parent,
        text=text,
        bd=0,
        relief=tk.FLAT,
        padx=22,
        pady=8,
        cursor="hand2",
        font=ui_font(10, bold=True),
        bg=ACCENT,
        fg="#ffffff",
        activebackground=ACCENT_ACTIVE,
        activeforeground="#ffffff",
        disabledforeground="#cbd5e1",
        highlightthickness=0,
    )

    def on_enter(_event: object) -> None:
        if btn.cget("state") == tk.NORMAL:
            btn.configure(bg=ACCENT_ACTIVE)

    def on_leave(_event: object) -> None:
        btn.configure(bg=ACCENT)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def make_secondary_button(parent: tk.Widget, text: str) -> tk.Button:
    """Return a neutral button used for ``Cancel`` actions in the card."""
    return tk.Button(
        parent,
        text=text,
        bd=0,
        relief=tk.FLAT,
        padx=18,
        pady=8,
        cursor="hand2",
        font=ui_font(10),
        bg=COMPOSER_BG,
        fg=CHAT_FG,
        activebackground=DIVIDER,
        activeforeground=CHAT_FG,
        highlightthickness=0,
    )


__all__ = [
    "SHELL_BG",
    "apply_setup_style",
    "make_card",
    "make_field_combo",
    "make_field_entry",
    "make_field_label",
    "make_primary_button",
    "make_secondary_button",
    "make_status_label",
]
