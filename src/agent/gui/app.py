"""Tkinter shell around :func:`drive_agent_turn` with threaded model calls."""

from __future__ import annotations

import threading
import traceback
from functools import partial
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

from dotenv import load_dotenv

from agent.gui._setup_style import make_primary_button
from agent.gui.bootstrap import session_header_text, start_session
from agent.gui.fonts import ui_font
from agent.gui.setup_dialog import (
    SetupResult,
    apply_setup_result,
    run_setup_dialog,
    setup_needs_prompt,
)
from agent.gui.shell import ShellWidgets, apply_global_style, build_chat_shell
from agent.gui.theme import ACCENT, ACCENT_ACTIVE, CHAT_FG, MUTED, SHELL_BG
from agent.gui.transcript_panel import TranscriptPanel
from agent.providers import Provider, ProviderName, resolved_llm_provider
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
        self._activity_visible = False

        self._needs_setup_overlay: tk.Frame | None = None
        self._needs_setup_msg_var = tk.StringVar(value="")

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

    def _ensure_activity_visible(self) -> None:
        """Show the indeterminate progress strip once per busy segment (main thread)."""
        if self._activity_visible:
            return
        self._activity_visible = True
        strip = self._widgets.activity_strip
        bar = self._widgets.activity_progress
        strip.pack(fill=tk.X, pady=(2, 0), before=self._status)
        bar.start()

    def _hide_activity_visible(self) -> None:
        """Stop and hide the progress strip (main thread)."""
        if not self._activity_visible:
            return
        self._activity_visible = False
        self._widgets.activity_progress.stop()
        self._widgets.activity_strip.pack_forget()

    def _on_working_phase(self, message: str) -> None:
        """Apply a status line from :func:`drive_agent_turn` ``working`` yields (main thread).

        Args:
            message: Human-readable description of the current step.
        """
        self._ensure_activity_visible()
        self._set_status(message)

    def _kickoff_bootstrap(self) -> None:
        """Run setup on the Tk thread, then finish provider build in the background.

        When the user cancels the setup dialog (or the environment cannot be
        resolved into a valid provider), the chat shell stays alive and a
        centered "Resume setup" overlay is shown instead of closing the app.
        """
        load_dotenv(Path.cwd() / ".env", override=False)
        provider_name = self._resolve_setup_on_main_thread()
        if provider_name is None:
            self._show_needs_setup_screen(
                "mini-agent needs a provider, API key, and model before it can chat.\n"
                "Click below to open the setup dialog again."
            )
            return
        self._hide_needs_setup_screen()
        self._set_status("Initializing…")
        threading.Thread(
            target=self._bootstrap_worker,
            args=(provider_name,),
            daemon=True,
        ).start()

    def _resolve_setup_on_main_thread(self) -> ProviderName | None:
        """Show the unified setup dialog (if needed) and return the provider id.

        Returns:
            Resolved provider id, or ``None`` if the user cancels the dialog
            or the environment holds an invalid value.
        """
        if not setup_needs_prompt():
            try:
                return resolved_llm_provider()
            except SystemExit as exc:
                messagebox.showerror("mini-agent", str(exc), parent=self._root)
                return None
        result: SetupResult | None = run_setup_dialog(self._root)
        if result is None:
            return None
        apply_setup_result(result)
        return result.provider

    def _bootstrap_worker(self, provider_name: ProviderName) -> None:
        """Build the model client off the UI thread after setup is complete.

        Args:
            provider_name: Resolved provider id from env or the setup dialog.
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
        """Report a startup error and offer to re-run setup without closing.

        Args:
            message: Error text (may be multi-line); shown in a modal alert.
                After dismissing the alert, the chat shell is covered by the
                "Resume setup" overlay so the user can adjust settings and
                try again instead of having the window closed.
        """
        messagebox.showerror("mini-agent", message, parent=self._root)
        self._show_needs_setup_screen(
            "mini-agent could not start a session with the configured provider.\n"
            "Adjust your settings and try again."
        )

    def _build_needs_setup_overlay(self) -> tk.Frame:
        """Create the centered "Resume setup" panel that covers the chat area.

        Returns:
            A :class:`tk.Frame` child of the shell, not yet ``place``-d. The
            frame contains a title, a wrapped message bound to
            ``self._needs_setup_msg_var``, and a primary "Resume setup" button.
        """
        frame = tk.Frame(self._widgets.shell, bg=SHELL_BG)
        inner = tk.Frame(frame, bg=SHELL_BG)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            inner,
            text="Setup is not complete",
            bg=SHELL_BG,
            fg=CHAT_FG,
            font=ui_font(16, bold=True),
        ).pack(pady=(0, 8))
        tk.Label(
            inner,
            textvariable=self._needs_setup_msg_var,
            bg=SHELL_BG,
            fg=MUTED,
            font=ui_font(11),
            wraplength=480,
            justify="center",
        ).pack(pady=(0, 20))

        btn = make_primary_button(inner, "Resume setup")
        btn.configure(command=self._on_resume_setup)
        btn.pack()
        return frame

    def _show_needs_setup_screen(self, message: str) -> None:
        """Cover the chat area with the "Resume setup" overlay.

        Args:
            message: Short explanation rendered above the button.
        """
        if self._needs_setup_overlay is None:
            self._needs_setup_overlay = self._build_needs_setup_overlay()
        self._needs_setup_msg_var.set(message)
        self._needs_setup_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self._needs_setup_overlay.lift()
        self._hide_activity_visible()
        self._set_ui_enabled(False)
        self._set_status("Setup required.")

    def _hide_needs_setup_screen(self) -> None:
        """Remove the resume-setup overlay if it is currently displayed."""
        if self._needs_setup_overlay is not None:
            self._needs_setup_overlay.place_forget()

    def _on_resume_setup(self) -> None:
        """Re-open the setup flow when the user clicks the resume button."""
        self._hide_needs_setup_screen()
        self._kickoff_bootstrap()

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
        self._ensure_activity_visible()
        self._set_status("Sending your message…")
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
                if kind == "working":
                    self._root.after(0, partial(self._on_working_phase, str(payload)))
                    continue
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
                self._hide_activity_visible()
                self._set_ui_enabled(True)
                self._set_status("Ready.")

            self._root.after(0, on_done)


def run_gui() -> None:
    """Start the Tkinter mini-agent window (blocks until the user closes it)."""
    root = tk.Tk()
    MiniAgentApp(root)
    root.mainloop()
