"""Main window layout: shell frame, transcript area, and composer bar."""

from __future__ import annotations

from dataclasses import dataclass

import tkinter as tk
from tkinter import scrolledtext, ttk

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


def apply_global_style() -> None:
    """Apply ttk theme and scrollbar styling used by the transcript widget."""
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "Vertical.TScrollbar",
        gripcount=0,
        background="#cbd5e1",
        troughcolor=CHAT_SURFACE,
        borderwidth=0,
        arrowsize=12,
    )
    style.map("Vertical.TScrollbar", background=[("active", "#94a3b8"), ("pressed", "#64748b")])
    style.configure(
        "MiniActivity.Horizontal.TProgressbar",
        troughcolor=COMPOSER_BG,
        background=ACCENT,
        thickness=5,
        borderwidth=0,
    )


@dataclass(frozen=True, slots=True)
class ShellWidgets:
    """References to the main chat shell widgets after :func:`build_chat_shell`."""

    shell: tk.Frame
    header: tk.Frame
    settings: tk.Button
    transcript: scrolledtext.ScrolledText
    composer: tk.Frame
    entry: tk.Entry
    send: tk.Button
    activity_strip: tk.Frame
    activity_progress: ttk.Progressbar
    status: tk.Label


def build_chat_shell(root: tk.Tk) -> ShellWidgets:
    """Create the shell, transcript, and bottom composer bar under ``root``.

    Does not wire the Send command or transcript behavior; the app attaches those.

    Args:
        root: Main Tk root window.

    Returns:
        Packed widgets for the chat UI.
    """
    shell = tk.Frame(root, bg=SHELL_BG)
    shell.pack(fill="both", expand=True)

    header = tk.Frame(shell, bg=SHELL_BG)
    settings = tk.Button(
        header,
        text="\u2699",
        bd=0,
        relief=tk.FLAT,
        padx=10,
        pady=2,
        cursor="hand2",
        font=ui_font(14),
        bg=SHELL_BG,
        fg=MUTED,
        activebackground=DIVIDER,
        activeforeground=CHAT_FG,
        disabledforeground="#cbd5e1",
        highlightthickness=0,
    )

    transcript = scrolledtext.ScrolledText(
        shell,
        wrap="word",
        state=tk.NORMAL,
        font=ui_font(11),
        bg=CHAT_SURFACE,
        fg=CHAT_FG,
        insertbackground=CHAT_FG,
        insertwidth=0,
        cursor="arrow",
        borderwidth=0,
        highlightthickness=0,
        padx=14,
        pady=16,
        selectbackground="#bfdbfe",
        selectforeground=CHAT_FG,
    )

    composer = tk.Frame(
        shell,
        bg=COMPOSER_BG,
        highlightthickness=1,
        highlightbackground=DIVIDER,
    )
    input_row = tk.Frame(composer, bg=COMPOSER_BG)
    entry = tk.Entry(
        input_row,
        bd=0,
        relief=tk.FLAT,
        highlightthickness=2,
        highlightcolor=ACCENT,
        highlightbackground=DIVIDER,
        bg="#ffffff",
        fg=CHAT_FG,
        insertbackground=CHAT_FG,
        font=ui_font(11),
        disabledbackground="#f1f5f9",
        disabledforeground="#94a3b8",
    )
    send = tk.Button(
        input_row,
        text="Send",
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
    activity_strip = tk.Frame(composer, bg=COMPOSER_BG)
    activity_progress = ttk.Progressbar(
        activity_strip,
        mode="indeterminate",
        style="MiniActivity.Horizontal.TProgressbar",
    )
    activity_progress.pack(fill=tk.X, padx=14, pady=(4, 0))

    status = tk.Label(
        composer,
        text="Starting…",
        anchor="w",
        bg=COMPOSER_BG,
        fg=MUTED,
        font=ui_font(9),
    )

    header.pack(side=tk.TOP, fill=tk.X)
    settings.pack(side=tk.RIGHT, padx=10, pady=6)

    composer.pack(side=tk.BOTTOM, fill=tk.X)
    transcript.pack(fill="both", expand=True, padx=0, pady=0)

    input_row.pack(fill=tk.X, padx=14, pady=(12, 4))
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=8)
    send.pack(side=tk.RIGHT)

    status.pack(fill=tk.X, padx=14, pady=(0, 10))

    return ShellWidgets(
        shell=shell,
        header=header,
        settings=settings,
        transcript=transcript,
        composer=composer,
        entry=entry,
        send=send,
        activity_strip=activity_strip,
        activity_progress=activity_progress,
        status=status,
    )
