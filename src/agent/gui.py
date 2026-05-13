"""Tkinter front-end for the mini-agent conversation loop (chat-style UI)."""

from __future__ import annotations

import json
import os
import threading
import traceback
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import cast

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from dotenv import load_dotenv

from agent.gui_markdown import insert_markdown
from agent.prompt import (
    collect_guide_paths_walking_up,
    format_new_guide_sections,
    system_prompt,
)
from agent.providers import AVAILABLE_PROVIDERS, Provider, ProviderName, build_provider
from agent.providers._shared import write_env_value
from agent.runner import drive_agent_turn

# Messenger-inspired light palette
_CHAT_BG = "#e5ddd5"
_CHAT_FG = "#111b21"
_MUTED = "#667781"
_USER_BUBBLE = "#d9fdd3"
_ASSISTANT_BUBBLE = "#ffffff"
_TOOL_BUBBLE = "#fff8e1"
_CODE_INLINE_BG = "#eef1f4"
_CODE_BLOCK_BG = "#f0f2f5"
_LINK = "#0277bd"
_LABEL_USER = "#128c7e"


def _resolve_provider_name(root: tk.Tk) -> ProviderName | None:
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


def _start_session(provider_name: ProviderName) -> tuple[list[dict[str, str]], Provider, set[str]]:
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


def _ui_font(size: int, *, bold: bool = False, italic: bool = False, overstrike: bool = False) -> tuple:
    """Return a Tk font tuple for the current platform.

    Args:
        size: Point size.
        bold: Whether to use a bold weight.
        italic: Whether to use an oblique/slant style.
        overstrike: Whether to draw a strikethrough line.

    Returns:
        Tk ``font`` tuple accepted by ``Text.tag_configure``.
    """
    family = "Segoe UI" if os.name == "nt" else "Helvetica"
    style: list[str] = []
    if bold:
        style.append("bold")
    if italic:
        style.append("italic")
    if overstrike:
        style.append("overstrike")
    if style:
        return (family, size, " ".join(style))
    return (family, size)


def _mono_font(size: int, *, bold: bool = False) -> tuple:
    """Return a monospace font tuple.

    Args:
        size: Point size.
        bold: Whether to request bold weight.

    Returns:
        Tk font tuple.
    """
    family = "Consolas" if os.name == "nt" else "Menlo"
    if bold:
        return (family, size, "bold")
    return (family, size)


class MiniAgentApp:
    """Tkinter shell around :func:`drive_agent_turn` with threaded model calls."""

    def __init__(self, root: tk.Tk) -> None:
        """Lay out widgets and start background provider initialization.

        Args:
            root: Main Tk root window.
        """
        self._root = root
        root.title("mini-agent")
        root.geometry("760x560")
        root.minsize(480, 360)
        root.configure(bg=_CHAT_BG)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Chat.TEntry", fieldbackground=_ASSISTANT_BUBBLE, foreground=_CHAT_FG)
        style.configure("Chat.TButton", padding=6)
        style.configure("Chat.TLabel", background=_CHAT_BG, foreground=_MUTED)

        self._shell = tk.Frame(root, bg=_CHAT_BG)
        self._shell.pack(fill="both", expand=True)

        self._transcript = scrolledtext.ScrolledText(
            self._shell,
            wrap="word",
            state="disabled",
            font=_ui_font(10),
            bg=_CHAT_BG,
            fg=_CHAT_FG,
            insertbackground=_CHAT_FG,
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=12,
            selectbackground="#b3d7ff",
            selectforeground=_CHAT_FG,
        )
        self._transcript.pack(fill="both", expand=True, padx=0, pady=(4, 0))
        self._setup_chat_tags()

        input_row = tk.Frame(self._shell, bg=_CHAT_BG)
        input_row.pack(fill="x", padx=10, pady=(6, 10))
        self._entry = ttk.Entry(input_row, style="Chat.TEntry")
        self._entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=4)
        self._send = ttk.Button(input_row, text="Send", command=self._on_send, style="Chat.TButton")
        self._send.pack(side="right")

        self._status = ttk.Label(root, text="Starting…", anchor="w", style="Chat.TLabel")
        self._status.pack(fill="x", padx=12, pady=(0, 6))

        self._conversation: list[dict[str, str]] | None = None
        self._provider: Provider | None = None
        self._injected_guide_paths: set[str] | None = None
        self._busy = False

        self._entry.bind("<Return>", lambda _e: self._on_send())
        self._set_ui_enabled(False)

        self._root.after(0, self._kickoff_bootstrap)

    def _setup_chat_tags(self) -> None:
        """Define ``Text`` tags for chat bubbles, Markdown, and system lines."""
        t = self._transcript
        t.tag_configure("gutter", spacing1=2, spacing3=6)
        t.tag_configure("role_label_user", foreground=_LABEL_USER, font=_ui_font(9, bold=True))
        t.tag_configure("role_label_assistant", foreground=_MUTED, font=_ui_font(9, bold=True))
        t.tag_configure("role_label_tool", foreground="#b45309", font=_ui_font(9, bold=True))
        t.tag_configure(
            "bubble_user",
            background=_USER_BUBBLE,
            foreground=_CHAT_FG,
            spacing1=4,
            spacing3=6,
            lmargin1=96,
            lmargin2=96,
            rmargin=10,
            font=_ui_font(10),
        )
        t.tag_configure(
            "bubble_assistant",
            background=_ASSISTANT_BUBBLE,
            foreground=_CHAT_FG,
            spacing1=4,
            spacing3=6,
            lmargin1=10,
            lmargin2=10,
            rmargin=72,
            font=_ui_font(10),
        )
        t.tag_configure(
            "bubble_tool",
            background=_TOOL_BUBBLE,
            foreground=_CHAT_FG,
            spacing1=4,
            spacing3=6,
            lmargin1=10,
            lmargin2=10,
            rmargin=72,
            font=_mono_font(9),
        )
        t.tag_configure("system_meta", foreground=_MUTED, font=_ui_font(9))
        t.tag_configure("md_bold", font=_ui_font(10, bold=True))
        t.tag_configure("md_italic", font=_ui_font(10, italic=True))
        t.tag_configure("md_strike", font=_ui_font(10, overstrike=True))
        t.tag_configure("md_code", font=_mono_font(9), background=_CODE_INLINE_BG)
        t.tag_configure("md_code_lang", font=_ui_font(8), foreground=_MUTED)
        t.tag_configure(
            "md_code_block",
            font=_mono_font(9),
            background=_CODE_BLOCK_BG,
            spacing1=4,
            spacing3=4,
            lmargin1=8,
            lmargin2=8,
        )
        t.tag_configure("md_h1", font=_ui_font(13, bold=True), spacing3=4)
        t.tag_configure("md_h2", font=_ui_font(12, bold=True), spacing3=2)
        t.tag_configure("md_h3", font=_ui_font(11, bold=True), spacing3=2)
        t.tag_configure("md_list", font=_ui_font(10))
        t.tag_configure("md_quote", font=_ui_font(10, italic=True), foreground="#37474f")
        t.tag_configure("md_link", foreground=_LINK, underline=True, font=_ui_font(10))
        t.tag_configure("md_link_url", foreground=_MUTED, font=_ui_font(8))

    def _transcript_do(self, work: Callable[[], None]) -> None:
        """Temporarily enable the transcript, run ``work``, then lock and scroll.

        Args:
            work: Callable that performs ``Text`` inserts on ``self._transcript``.
        """
        self._transcript.configure(state="normal")
        try:
            work()
        finally:
            self._transcript.configure(state="disabled")
            self._transcript.see("end")

    def _append_user_message(self, text: str) -> None:
        """Render a user turn as a right-weighted bubble with Markdown.

        Args:
            text: Raw user message (Markdown allowed).
        """

        def work() -> None:
            w = self._transcript
            w.insert("end", "\n", ("gutter",))
            w.insert("end", "You\n", ("role_label_user",))
            insert_markdown(w, text, ("bubble_user",))
            w.insert("end", "\n", ("gutter",))

        self._transcript_do(work)

    def _append_assistant_message(self, markdown: str) -> None:
        """Render an assistant reply with Markdown in a left bubble.

        Args:
            markdown: Assistant message (Markdown).
        """

        def work() -> None:
            w = self._transcript
            w.insert("end", "\n", ("gutter",))
            w.insert("end", "Assistant\n", ("role_label_assistant",))
            insert_markdown(w, markdown, ("bubble_assistant",))
            w.insert("end", "\n", ("gutter",))

        self._transcript_do(work)

    def _append_tool_card(self, name: str, args: object) -> None:
        """Show a tool invocation in a compact monospace card.

        Args:
            name: Tool name.
            args: Arguments object (typically a ``dict``) to pretty-print as JSON.
        """

        def work() -> None:
            w = self._transcript
            w.insert("end", "\n", ("gutter",))
            w.insert("end", f"Tool · {name}\n", ("role_label_tool",))
            try:
                body = json.dumps(args, indent=2, ensure_ascii=False)
            except TypeError:
                body = repr(args)
            w.insert("end", body + "\n", ("bubble_tool",))
            w.insert("end", "\n", ("gutter",))

        self._transcript_do(work)

    def _append_system_banner(self, text: str) -> None:
        """Append a plain multi-line status banner (not Markdown).

        Args:
            text: Human-readable intro text.
        """

        def work() -> None:
            self._transcript.insert("end", text + "\n", ("system_meta",))

        self._transcript_do(work)

    def _kickoff_bootstrap(self) -> None:
        """Resolve provider on the Tk thread, then finish setup in the background."""
        load_dotenv(Path.cwd() / ".env", override=False)
        provider_name = _resolve_provider_name(self._root)
        if provider_name is None:
            self._root.destroy()
            return
        threading.Thread(
            target=self._bootstrap_worker,
            args=(provider_name,),
            daemon=True,
        ).start()

    def _set_ui_enabled(self, enabled: bool) -> None:
        """Enable or disable message entry while a request is in flight.

        Args:
            enabled: Whether the user can type and send.
        """
        state = "normal" if enabled else "disabled"
        self._entry.configure(state=state)
        self._send.configure(state=state)

    def _set_status(self, text: str) -> None:
        """Update the footer status line on the Tk main thread.

        Args:
            text: Short status message.
        """
        self._status.configure(text=text)

    def _bootstrap_worker(self, provider_name: ProviderName) -> None:
        """Build the model client off the UI thread after provider id is known.

        Args:
            provider_name: Resolved provider id from env or the Tk picker.
        """
        try:
            conversation, provider, injected = _start_session(provider_name)
            cwd = Path.cwd()
            header = (
                f"Working directory: {cwd}\n"
                f"Provider: {provider.name} — model: {provider.model}\n"
                "Type a message below; assistant replies support Markdown "
                "(headings, lists, links, code fences, emphasis).\n"
            )

            def on_ready() -> None:
                self._conversation = conversation
                self._provider = provider
                self._injected_guide_paths = injected
                self._append_system_banner(header)
                self._set_status("Ready.")
                self._set_ui_enabled(True)
                self._entry.focus_set()

            self._root.after(0, on_ready)
        except SystemExit as exc:
            msg = str(exc) or "Setup failed."
            self._root.after(0, lambda: self._show_fatal(msg))
        except BaseException as exc:
            detail = "".join(traceback.format_exception(exc))
            self._root.after(0, lambda: self._show_fatal(detail))

    def _show_fatal(self, message: str) -> None:
        """Show a startup error and close the app.

        Args:
            message: Error text (may be multi-line).
        """
        messagebox.showerror("mini-agent", message, parent=self._root)
        self._root.destroy()

    def _on_send(self) -> None:
        """Read the entry box and schedule a model turn on a worker thread."""
        if self._busy or self._conversation is None or self._provider is None:
            return
        text = self._entry.get().strip()
        if not text:
            return
        self._entry.delete(0, "end")
        self._busy = True
        self._set_ui_enabled(False)
        self._set_status("Thinking…")
        self._append_user_message(text)

        conv = self._conversation
        provider = self._provider
        injected = self._injected_guide_paths
        assert injected is not None

        threading.Thread(
            target=self._turn_worker,
            args=(conv, provider, injected, text),
            daemon=True,
        ).start()

    def _turn_worker(
        self,
        conversation: list[dict[str, str]],
        provider: Provider,
        injected_guide_paths: set[str],
        user_text: str,
    ) -> None:
        """Run one user message through tools and the model off the UI thread."""
        try:
            for kind, payload in drive_agent_turn(
                conversation, provider, injected_guide_paths, user_text
            ):
                if kind == "tool":
                    name, args, _result = payload
                    self._root.after(0, partial(self._append_tool_card, name, args))
                else:
                    reply = str(payload)
                    self._root.after(0, partial(self._append_assistant_message, reply))
        except SystemExit as exc:
            msg = str(exc) or "The model reported a fatal configuration error."
            self._root.after(0, lambda: messagebox.showerror("mini-agent", msg, parent=self._root))
        except BaseException:
            tb = traceback.format_exc()
            self._root.after(0, lambda: messagebox.showerror("mini-agent", tb, parent=self._root))
        finally:

            def on_done() -> None:
                self._busy = False
                self._set_ui_enabled(True)
                self._set_status("Ready.")

            self._root.after(0, on_done)


def run_gui() -> None:
    """Start the Tkinter mini-agent window (blocks until the user closes it)."""
    root = tk.Tk()
    MiniAgentApp(root)
    root.mainloop()
