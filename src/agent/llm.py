from __future__ import annotations

import json
from typing import Any

import anthropic

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


def call_llm(client: anthropic.Anthropic, conversation: list[dict[str, str]], model: str) -> str:
    """Send the conversation to Claude and return the assistant text.

    Args:
        client: Authenticated Anthropic client.
        conversation: Messages with roles ``system``, ``user``, and ``assistant``.
        model: Model id for ``messages.create``.

    Returns:
        Text content of the first response block, or a string representation
        if the block is not plain text.
    """
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=conversation[0]["content"],
        messages=conversation[1:],
    )
    block = response.content[0]
    return block.text if block.type == "text" else str(block)
