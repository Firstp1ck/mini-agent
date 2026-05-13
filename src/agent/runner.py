"""Interactive REPL that drives the agent loop.

The runner is provider-agnostic: it builds a :class:`agent.providers.Provider`
based on ``MINI_AGENT_PROVIDER`` and then only calls ``provider.call`` to
exchange messages. All vendor-specific behavior lives under
:mod:`agent.providers`.
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

from agent.llm import extract_tool_invocations
from agent.prompt import system_prompt
from agent.providers import build_provider, resolved_llm_provider
from agent.tools import TOOL_REGISTRY

YOU_COLOR = "\033[94m"
ASSISTANT_COLOR = "\033[93m"
TOOL_COLOR = "\033[90m"
RESET_COLOR = "\033[0m"


def run_agent() -> None:
    """Run the interactive REPL: read user input, call the model, run tools.

    Loads ``.env``, selects and configures a provider, then alternates between
    assistant replies and tool execution until a non-tool response is printed.
    """
    load_dotenv(Path.cwd() / ".env", override=False)
    provider = build_provider(resolved_llm_provider())
    conversation: list[dict[str, str]] = [{"role": "system", "content": system_prompt()}]

    print("Mini Agent. Ctrl-D or Ctrl-C to exit.")
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
                conversation.append({"role": "user", "content": f"tool_result({json.dumps(result)})"})
