"""Read-only chat transcript: bubble tags, margins, and Markdown append helpers."""

from __future__ import annotations

import json
from collections.abc import Callable

import tkinter as tk
from tkinter import scrolledtext

from agent.gui.fonts import mono_font, ui_font
from agent.gui.markdown import insert_markdown
from agent.gui.theme import (
    ASSISTANT_BUBBLE,
    CHAT_FG,
    CODE_BLOCK_BG,
    CODE_INLINE_BG,
    LABEL_TOOL,
    LABEL_USER,
    LINK,
    MARK_BG,
    MUTED,
    TOOL_BUBBLE,
    USER_BUBBLE,
)


def _raise_selection_above_content(widget: tk.Text) -> None:
    """Raise the selection tag so drag-highlight is visible on bubble backgrounds.

    Bubble tags set ``background``; if they sit above ``sel`` in Tk's tag order,
    the white/blue fill hides ``selectbackground`` and selection looks broken.

    Args:
        widget: Transcript ``Text`` or ``ScrolledText``.
    """
    widget.tag_raise(tk.SEL)


class TranscriptPanel:
    """Owns transcript ``Text`` tags, resize margins, read-only input filtering, and appends."""

    def __init__(self, transcript: scrolledtext.ScrolledText) -> None:
        """Configure tags and bindings on the given transcript widget.

        Args:
            transcript: Packed ``ScrolledText`` used as the chat log.
        """
        self._transcript = transcript
        self._last_transcript_width = 0
        self._setup_chat_tags()
        transcript.bind("<Key>", self._on_transcript_readonly_key, add="+")
        transcript.bind("<<Paste>>", lambda _e: "break", add="+")
        transcript.bind("<Configure>", self._on_transcript_configure, add="+")

    def schedule_initial_margin_sync(self) -> None:
        """Defer first bubble margin pass until the widget has a real width."""
        self._transcript.after_idle(self.initial_margin_sync)

    def initial_margin_sync(self) -> None:
        """Apply bubble margins once the transcript has a non-trivial width."""
        width = self._transcript.winfo_width()
        if width > 40:
            self._last_transcript_width = width
            self._sync_bubble_margins(width)

    def _on_transcript_configure(self, event: object) -> None:
        """Keep user/assistant bubble widths in proportion when the window resizes."""
        widget = getattr(event, "widget", None)
        if widget is not self._transcript:
            return
        width = int(getattr(event, "width", 0))
        if width <= 40 or width == self._last_transcript_width:
            return
        self._last_transcript_width = width
        self._sync_bubble_margins(width)

    def _sync_bubble_margins(self, width: int) -> None:
        """Narrow bubble columns so messages do not read as full-width bars.

        Args:
            width: Current inner width of the transcript ``Text`` widget in pixels.
        """
        edge = 14
        max_bubble = min(520, int(width * 0.82))
        user_left = max(edge * 3, width - max_bubble - edge)
        asst_right = max(edge * 3, width - max_bubble - edge)
        t = self._transcript
        t.tag_configure("bubble_user", lmargin1=user_left, lmargin2=user_left, rmargin=edge)
        t.tag_configure("role_label_user", lmargin1=user_left, lmargin2=user_left, rmargin=edge)
        t.tag_configure("bubble_assistant", lmargin1=edge, lmargin2=edge, rmargin=asst_right)
        t.tag_configure("role_label_assistant", lmargin1=edge, lmargin2=edge, rmargin=asst_right)
        t.tag_configure("bubble_tool", lmargin1=edge, lmargin2=edge, rmargin=asst_right)
        t.tag_configure("role_label_tool", lmargin1=edge, lmargin2=edge, rmargin=asst_right)
        _raise_selection_above_content(t)

    def _on_transcript_readonly_key(self, event: tk.Event) -> str | None:
        """Block edits in the transcript while keeping selection and copy shortcuts.

        A ``disabled`` transcript often cannot be selected on Windows; we keep
        ``state=normal`` and reject modifying keys instead.

        Args:
            event: Tk key event for the transcript ``Text`` widget.

        Returns:
            ``\"break\"`` to suppress the keystroke, or ``None`` to allow it.
        """
        ks = event.keysym or ""
        state = int(event.state or 0)
        ctrl = bool(state & 0x4)
        command = bool(state & 0x8)
        accel = ctrl or command
        if accel and ks.lower() in ("c", "a", "insert"):
            return None
        if accel and ks.lower() in ("v", "x"):
            return "break"
        if ks in (
            "Left",
            "Right",
            "Up",
            "Down",
            "Home",
            "End",
            "Prior",
            "Next",
            "KP_Left",
            "KP_Right",
            "KP_Up",
            "KP_Down",
            "KP_Home",
            "KP_End",
            "KP_Prior",
            "KP_Next",
        ):
            return None
        if ks in ("BackSpace", "Delete", "Return", "KP_Enter", "Tab"):
            return "break"
        if event.char and event.char.isprintable():
            return "break"
        return None

    def _setup_chat_tags(self) -> None:
        """Define ``Text`` tags for chat bubbles, Markdown, and system lines."""
        t = self._transcript
        t.tag_configure("gutter", spacing1=4, spacing3=10)
        t.tag_configure("role_label_user", foreground=LABEL_USER, font=ui_font(9, bold=True))
        t.tag_configure("role_label_assistant", foreground=MUTED, font=ui_font(9, bold=True))
        t.tag_configure("role_label_tool", foreground=LABEL_TOOL, font=ui_font(9, bold=True))
        t.tag_configure(
            "bubble_user",
            background=USER_BUBBLE,
            foreground=CHAT_FG,
            spacing1=6,
            spacing3=8,
            lmargin1=180,
            lmargin2=180,
            rmargin=14,
            font=ui_font(11),
        )
        t.tag_configure(
            "bubble_assistant",
            background=ASSISTANT_BUBBLE,
            foreground=CHAT_FG,
            spacing1=6,
            spacing3=8,
            lmargin1=14,
            lmargin2=14,
            rmargin=180,
            font=ui_font(11),
        )
        t.tag_configure(
            "bubble_tool",
            background=TOOL_BUBBLE,
            foreground=CHAT_FG,
            spacing1=6,
            spacing3=8,
            lmargin1=14,
            lmargin2=14,
            rmargin=180,
            font=mono_font(10),
        )
        t.tag_configure(
            "system_meta",
            foreground=MUTED,
            font=ui_font(9),
            background="#e8ecf4",
            spacing1=10,
            spacing3=10,
            lmargin1=14,
            lmargin2=14,
            rmargin=14,
        )
        t.tag_configure("md_bold", font=ui_font(11, bold=True))
        t.tag_configure("md_italic", font=ui_font(11, italic=True))
        t.tag_configure("md_strike", font=ui_font(11, overstrike=True))
        t.tag_configure("md_mark", background=MARK_BG)
        t.tag_configure("md_code", font=mono_font(10), background=CODE_INLINE_BG)
        t.tag_configure("md_code_lang", font=ui_font(8), foreground=MUTED)
        t.tag_configure(
            "md_code_block",
            font=mono_font(10),
            background=CODE_BLOCK_BG,
            spacing1=6,
            spacing3=6,
            lmargin1=6,
            lmargin2=6,
        )
        t.tag_configure("md_h1", font=ui_font(14, bold=True), spacing3=6)
        t.tag_configure("md_h2", font=ui_font(13, bold=True), spacing3=4)
        t.tag_configure("md_h3", font=ui_font(12, bold=True), spacing3=4)
        t.tag_configure("md_list", font=ui_font(11))
        t.tag_configure("md_quote", font=ui_font(11, italic=True), foreground="#475569")
        t.tag_configure("md_link", foreground=LINK, underline=True, font=ui_font(11))
        t.tag_configure("md_link_url", foreground=MUTED, font=ui_font(8))
        _raise_selection_above_content(t)

    def transcript_do(self, work: Callable[[], None]) -> None:
        """Run ``work`` while the transcript accepts inserts, then scroll to the end.

        The transcript stays ``normal`` (not ``disabled``) so assistant text can be
        selected and copied on Windows; edits are blocked by
        :meth:`_on_transcript_readonly_key`.

        Args:
            work: Callable that performs ``Text`` inserts on the transcript widget.
        """
        self._transcript.configure(state=tk.NORMAL)
        try:
            work()
        finally:
            self._transcript.see("end")

    def append_user_message(self, text: str) -> None:
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

        self.transcript_do(work)

    def append_assistant_message(self, markdown: str) -> None:
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

        self.transcript_do(work)

    def append_tool_card(self, name: str, args: object) -> None:
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

        self.transcript_do(work)

    def append_system_banner(self, text: str) -> None:
        """Append a plain multi-line status banner (not Markdown).

        Args:
            text: Human-readable intro text.
        """

        def work() -> None:
            self._transcript.insert("end", text + "\n", ("system_meta",))

        self.transcript_do(work)
