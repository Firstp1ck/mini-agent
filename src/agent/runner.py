"""Interactive REPL that drives the agent loop.

The runner is provider-agnostic: it builds a :class:`agent.providers.Provider`
based on ``MINI_AGENT_PROVIDER`` and then only calls ``provider.call`` to
exchange messages. All vendor-specific behavior lives under
:mod:`agent.providers`.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agent.llm import extract_tool_invocations
from agent.prompt import (
    collect_guide_paths_walking_up,
    format_new_guide_sections,
    system_prompt,
)
from agent.providers import Provider, build_provider, resolved_llm_provider
from agent.tools import TOOL_REGISTRY, work_directories_for_tool

YOU_COLOR = "\033[94m"
ASSISTANT_COLOR = "\033[93m"
TOOL_COLOR = "\033[90m"
RESET_COLOR = "\033[0m"


def _ellipsize_plain_line(text: str, max_len: int) -> str:
    """Collapse runs of whitespace to single spaces and cap length with an ellipsis.

    Args:
        text: Arbitrary text (may contain newlines).
        max_len: Maximum length of the returned string (including ellipsis when trimmed).

    Returns:
        A single-line string at most ``max_len`` characters.
    """
    one_line = " ".join(text.split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 1] + "…"


def _working_message_for_model() -> str:
    """Return a short status line while blocked on the LLM."""
    return "Waiting for the model…"


def _working_message_for_tool(name: str, args: dict[str, Any]) -> str:
    """Return a short status line while a tool runs (for GUI status text).

    Args:
        name: Tool name from :data:`agent.tools.TOOL_REGISTRY`.
        args: Keyword arguments passed to the tool.

    Returns:
        Human-readable, single-line summary.
    """
    if name == "read_file":
        raw = args.get("filename")
        if isinstance(raw, str) and raw.strip():
            tip = Path(raw).name or raw.strip()
            return f"Reading file «{_ellipsize_plain_line(tip, 48)}»…"
        return "Reading a file…"

    if name == "list_files":
        raw = args.get("path", ".")
        if isinstance(raw, str) and raw.strip():
            tip = Path(raw).name or raw.strip() or "."
            return f"Listing folder «{_ellipsize_plain_line(tip, 44)}»…"
        return "Listing a folder…"

    if name == "edit_file":
        raw = args.get("path")
        old = args.get("old_str", "")
        if isinstance(raw, str) and raw.strip():
            tip = Path(raw).name or raw.strip()
            action = "Creating" if old == "" else "Editing"
            return f"{action} «{_ellipsize_plain_line(tip, 40)}»…"
        return "Editing a file…"

    if name == "bash":
        raw = args.get("command")
        if isinstance(raw, str) and raw.strip():
            return f"Running command: {_ellipsize_plain_line(raw, 52)}"
        return "Running a shell command…"

    return f"Running tool «{name}»…"


def _repl_exit_hint() -> str:
    """Return how to leave the REPL on this OS (EOF differs on Windows vs Unix)."""
    if sys.platform == "win32":
        return "Ctrl-Z then Enter, or Ctrl-C, to exit."
    return "Ctrl-D or Ctrl-C to exit."


def drive_agent_turn(
    conversation: list[dict[str, str]],
    provider: Provider,
    injected_guide_paths: set[str],
    user_text: str,
) -> Iterator[tuple[str, Any]]:
    """Append one user message and advance the loop until a plain assistant reply.

    This mirrors the CLI tool loop: the model may return tool invocations; each
    is executed, results are appended, and ``provider.call`` runs again until the
    reply contains no tools.

    Args:
        conversation: In-out transcript including the system message at index 0.
        provider: Configured LLM backend.
        injected_guide_paths: Mutable set tracking which guide files were merged
            into the system prompt (same semantics as the REPL).
        user_text: Non-empty user message for this turn.

    Yields:
        ``("working", status_text)`` before each model call and before each tool
        execution (intended for progress UI; safe to ignore in CLI).
        ``("tool", (tool_name, args_dict, result))`` for each executed tool, then
        ``("assistant", assistant_text)`` once when the model returns a non-tool
        reply. The conversation is updated before each yield.

    Raises:
        KeyError: If the model requests an unknown tool name (same as direct
            registry lookup).
    """
    conversation.append({"role": "user", "content": user_text})
    while True:
        yield ("working", _working_message_for_model())
        assistant_text = provider.call(conversation)
        invocations = extract_tool_invocations(assistant_text)
        if not invocations:
            conversation.append({"role": "assistant", "content": assistant_text})
            yield ("assistant", assistant_text)
            return

        conversation.append({"role": "assistant", "content": assistant_text})
        for name, args in invocations:
            yield ("working", _working_message_for_tool(name, args))
            result = TOOL_REGISTRY[name](**args)
            guide_candidates: list[Path] = []
            for directory in work_directories_for_tool(name, args):
                guide_candidates.extend(collect_guide_paths_walking_up(directory))
            extra_suffix, _ = format_new_guide_sections(
                guide_candidates, injected_guide_paths
            )
            if extra_suffix:
                conversation[0]["content"] += extra_suffix
            yield ("tool", (name, args, result))
            conversation.append(
                {"role": "user", "content": f"tool_result({json.dumps(result)})"}
            )


def run_agent() -> None:
    """Run the interactive REPL: read user input, call the model, run tools.

    Loads ``.env``, selects and configures a provider, then alternates between
    assistant replies and tool execution until a non-tool response is printed.
    """
    load_dotenv(Path.cwd() / ".env", override=False)
    provider = build_provider(resolved_llm_provider())
    injected_guide_paths: set[str] = set()
    initial_suffix, _ = format_new_guide_sections(
        collect_guide_paths_walking_up(Path.cwd()), injected_guide_paths
    )
    conversation: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt() + initial_suffix}
    ]

    print(f"Mini Agent using {provider.name} ({provider.model}) in {Path.cwd()}.")
    print(_repl_exit_hint())
    while True:
        try:
            user_input = input(f"{YOU_COLOR}You:{RESET_COLOR} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not user_input:
            continue

        for kind, payload in drive_agent_turn(
            conversation, provider, injected_guide_paths, user_input
        ):
            if kind == "working":
                continue
            if kind == "tool":
                name, args, _result = payload
                print(f"{TOOL_COLOR}tool: {name}({json.dumps(args)}){RESET_COLOR}")
            else:
                print(f"{ASSISTANT_COLOR}Assistant:{RESET_COLOR} {payload}")
