from __future__ import annotations

import inspect

from agent.tools import TOOL_REGISTRY

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
    tool = TOOL_REGISTRY[tool_name]
    return f"Name: {tool_name}\nDescription: {inspect.getdoc(tool)}\nSignature: {inspect.signature(tool)}"


def system_prompt() -> str:
    tools = "\n\n".join(tool_description(name) for name in TOOL_REGISTRY)
    return SYSTEM_PROMPT.format(tool_list_repr=tools)
