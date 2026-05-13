"""Interactive REPL that drives the agent loop.

The runner is provider-agnostic: it builds a :class:`agent.providers.Provider`
based on ``MINI_AGENT_PROVIDER`` and then only calls ``provider.call`` to
exchange messages. All vendor-specific behavior lives under
:mod:`agent.providers`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent.llm import extract_tool_invocations
from agent.prompt import (
    collect_guide_paths_walking_up,
    format_new_guide_sections,
    system_prompt,
)
from agent.providers import build_provider, resolved_llm_provider
from agent.tools import TOOL_REGISTRY, work_directories_for_tool

YOU_COLOR = "\033[94m"
ASSISTANT_COLOR = "\033[93m"
TOOL_COLOR = "\033[90m"
RESET_COLOR = "\033[0m"


def _repl_exit_hint() -> str:
    """Return how to leave the REPL on this OS (EOF differs on Windows vs Unix)."""
    if sys.platform == "win32":
        return "Ctrl-Z then Enter, or Ctrl-C, to exit."
    return "Ctrl-D or Ctrl-C to exit."


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

        conversation.append({"role": "user", "content": user_input})
        while True:
            assistant_text = provider.call(conversation)

            invocations = extract_tool_invocations(assistant_text)
            if not invocations:
                print(f"{ASSISTANT_COLOR}Assistant:{RESET_COLOR} {assistant_text}")
                conversation.append({"role": "assistant", "content": assistant_text})
                break

            conversation.append({"role": "assistant", "content": assistant_text})
            for name, args in invocations:
                print(f"{TOOL_COLOR}tool: {name}({json.dumps(args)}){RESET_COLOR}")
                result = TOOL_REGISTRY[name](**args)
                guide_candidates: list[Path] = []
                for directory in work_directories_for_tool(name, args):
                    guide_candidates.extend(collect_guide_paths_walking_up(directory))
                extra_suffix, _ = format_new_guide_sections(
                    guide_candidates, injected_guide_paths
                )
                if extra_suffix:
                    conversation[0]["content"] += extra_suffix
                conversation.append({"role": "user", "content": f"tool_result({json.dumps(result)})"})
