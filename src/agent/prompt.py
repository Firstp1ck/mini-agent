from __future__ import annotations

import inspect
from collections.abc import Sequence
from pathlib import Path

from agent.tools import TOOL_REGISTRY

# Filenames (in order) checked in each directory when walking upward for project context.
PROJECT_GUIDE_FILENAMES: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md")

SYSTEM_PROMPT = """
You are a minimal coding assistant that helps with small coding tasks.
You can inspect and edit files by asking this program to run tools locally.

Available tools:
{tool_list_repr}

Rules:
- When you need a tool, reply with exactly one line and nothing else:
  tool: TOOL_NAME({{"arg": "value"}})
- Use compact single-line JSON with double quotes.
- After receiving tool_result(...), continue the task.
- Prefer reading/listing before editing existing files.
- If no tool is needed, respond normally.
""".strip()


def tool_description(tool_name: str) -> str:
    """Build a human-readable description of one registered tool for the system prompt.

    Args:
        tool_name: Key present in ``TOOL_REGISTRY``.

    Returns:
        Multi-line string with name, docstring, and callable signature.
    """
    tool = TOOL_REGISTRY[tool_name]
    return f"Name: {tool_name}\nDescription: {inspect.getdoc(tool)}\nSignature: {inspect.signature(tool)}"


def system_prompt() -> str:
    """Return the system prompt including rules and all tool descriptions.

    Returns:
        Formatted ``SYSTEM_PROMPT`` with ``{tool_list_repr}`` filled in.
    """
    tools = "\n\n".join(tool_description(name) for name in TOOL_REGISTRY)
    return SYSTEM_PROMPT.format(tool_list_repr=tools)


def collect_guide_paths_walking_up(start: Path) -> list[Path]:
    """List ``AGENTS.md`` / ``CLAUDE.md`` paths from ``start`` through parents, nearest first.

    For each directory on the walk (including the starting directory), any of
    ``PROJECT_GUIDE_FILENAMES`` that exist as regular files are appended in that
    filename order. The walk stops at the filesystem root.

    Args:
        start: File or directory path; files use their parent directory as the
            first step.

    Returns:
        Resolved absolute paths to guide files, nearest directory first, without
        duplicates.
    """
    start_resolved = start.expanduser().resolve()
    if start_resolved.is_dir():
        directory = start_resolved
    else:
        directory = start_resolved.parent
    seen: set[str] = set()
    ordered: list[Path] = []
    current = directory
    while True:
        for name in PROJECT_GUIDE_FILENAMES:
            candidate = (current / name).resolve()
            if not candidate.is_file():
                continue
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(candidate)
        if current == current.parent:
            break
        current = current.parent
    return ordered


def format_new_guide_sections(
    candidate_paths: Sequence[Path], already_injected: set[str]
) -> tuple[str, set[str]]:
    """Build markdown sections for guide files not yet listed in ``already_injected``.

    Readable UTF-8 text is appended; unreadable paths are skipped.

    Args:
        candidate_paths: Guide files to consider, typically from
            :func:`collect_guide_paths_walking_up`.
        already_injected: Resolved path strings already merged into the system
            message; updated in-place with each newly formatted file.

    Returns:
        ``(suffix, newly_added_keys)`` where ``suffix`` is text to append to the
        system prompt and ``newly_added_keys`` is the set of resolved path strings
        added to ``already_injected``.
    """
    newly_added: set[str] = set()
    parts: list[str] = []
    for path in candidate_paths:
        key = str(path.resolve())
        if key in already_injected:
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        already_injected.add(key)
        newly_added.add(key)
        parts.append(
            f"\n\n---\n## Project context ({path.name})\n\nLocation: `{path}`\n\n{body}"
        )
    return "".join(parts), newly_added
