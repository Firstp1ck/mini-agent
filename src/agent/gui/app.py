"""Tkinter shell around :func:`drive_agent_turn` with threaded model calls."""

from __future__ import annotations

import threading
import traceback
from functools import partial
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

from dotenv import load_dotenv

from agent.gui.bootstrap import (
    resolve_provider_name,
    session_header_text,
    start_session,
)
from agent.gui.shell import ShellWidgets, apply_global_style, build_chat_shell
from agent.gui.theme import ACCENT, ACCENT_ACTIVE, SHELL_BG
from agent.gui.transcript_panel import TranscriptPanel
from agent.providers import Provider, ProviderName
from agent.runner import drive_agent_turn


class MiniAgentApp:
    """Main chat window: layout, transcript bubbles, and threaded agent turns."""

    def __init__(self, root: tk.Tk) -> None:
        """Lay out widgets and start background provider initialization.

        Args:
            root: Main Tk root window.
        """
        self._root = root
        root.title("mini-agent")
        root.geometry("800x600")
        root.minsize(520, 380)
        root.configure(bg=SHELL_BG)

        apply_global_style()
        self._widgets: ShellWidgets = build_chat_shell(root)
        self._transcript_panel = TranscriptPanel(self._widgets.transcript)
        self._transcript_panel.schedule_initial_margin_sync()

        self._entry = self._widgets.entry
        self._send = self._widgets.send
        self._status = self._widgets.status

        self._send.configure(command=self._on_send)
        self._send.bind("<Enter>", self._on_send_pointer_enter)
        self._send.bind("<Leave>", self._on_send_pointer_leave)

        self._conversation: list[dict[str, str]] | None = None
        self._provider: Provider | None = None
        self._injected_guide_paths: set[str] | None = None
        self._busy = False

        self._entry.bind("<Return>", lambda _e: self._on_send())
        self._set_ui_enabled(False)

        self._root.after(0, self._kickoff_bootstrap)

    def _on_send_pointer_enter(self, _event: object) -> None:
        """Brighten the Send button while the pointer is over it (when enabled)."""
        if self._send["state"] == tk.NORMAL:
            self._send.configure(bg=ACCENT_ACTIVE)

    def _on_send_pointer_leave(self, _event: object) -> None:
        """Restore the Send button color when the pointer leaves."""
        self._send.configure(bg=ACCENT)

    def _set_ui_enabled(self, enabled: bool) -> None:
        """Enable or disable message entry while a request is in flight.

        Args:
            enabled: Whether the user can type and send.
        """
        state = tk.NORMAL if enabled else tk.DISABLED
        self._entry.configure(state=state)
        self._send.configure(state=state)

    def _set_status(self, text: str) -> None:
        """Update the footer status line on the Tk main thread.

        Args:
            text: Short status message.
        """
        self._status.configure(text=text)

    def _kickoff_bootstrap(self) -> None:
        """Resolve provider on the Tk thread, then finish setup in the background."""
        load_dotenv(Path.cwd() / ".env", override=False)
        provider_name = resolve_provider_name(self._root)
        if provider_name is None:
            self._root.destroy()
            return
        threading.Thread(
            target=self._bootstrap_worker,
            args=(provider_name,),
            daemon=True,
        ).start()

    def _bootstrap_worker(self, provider_name: ProviderName) -> None:
        """Build the model client off the UI thread after provider id is known.

        Args:
            provider_name: Resolved provider id from env or the Tk picker.
        """
        try:
            conversation, provider, injected = start_session(provider_name)
            cwd = Path.cwd()
            header = session_header_text(cwd, provider)

            def on_ready() -> None:
                self._conversation = conversation
                self._provider = provider
                self._injected_guide_paths = injected
                self._transcript_panel.append_system_banner(header)
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
        self._transcript_panel.append_user_message(text)

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
        panel = self._transcript_panel
        try:
            for kind, payload in drive_agent_turn(
                conversation, provider, injected_guide_paths, user_text
            ):
                if kind == "tool":
                    name, args, _result = payload
                    self._root.after(0, partial(panel.append_tool_card, name, args))
                else:
                    reply = str(payload)
                    self._root.after(0, partial(panel.append_assistant_message, reply))
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
