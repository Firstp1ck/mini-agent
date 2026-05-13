"""Provider-agnostic helpers shared by the agent loop.

Currently this is just the parser for tool invocation lines emitted by the
model. Each LLM backend lives under :mod:`agent.providers`.
"""

from __future__ import annotations

import json
from typing import Any

from agent.tools import TOOL_REGISTRY


def extract_tool_invocations(text: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse ``tool: NAME({...})`` lines from assistant text.

    Args:
        text: Full assistant message; each line may contain one tool invocation.

    Returns:
        List of ``(tool_name, args_dict)`` for registered tools with valid JSON.
    """
    invocations: list[tuple[str, dict[str, Any]]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("tool:"):
            continue
        try:
            name, rest = line.removeprefix("tool:").strip().split("(", 1)
            if not rest.endswith(")"):
                continue
            args = json.loads(rest[:-1])
            if name.strip() in TOOL_REGISTRY and isinstance(args, dict):
                invocations.append((name.strip(), args))
        except Exception:
            continue
    return invocations
