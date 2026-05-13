from __future__ import annotations

import json
from typing import Any

import anthropic

from agent.tools import TOOL_REGISTRY


def extract_tool_invocations(text: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse lines formatted as: tool: name({"arg":"value"})."""
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
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=conversation[0]["content"],
        messages=conversation[1:],
    )
    block = response.content[0]
    return block.text if block.type == "text" else str(block)
