from __future__ import annotations

import json

import anthropic

from agent.config import DEFAULT_MODEL, ensure_anthropic_client, ensure_anthropic_model
from agent.llm import call_llm, extract_tool_invocations
from agent.prompt import system_prompt
from agent.tools import TOOL_REGISTRY

YOU_COLOR = "\033[94m"
ASSISTANT_COLOR = "\033[93m"
TOOL_COLOR = "\033[90m"
RESET_COLOR = "\033[0m"


def run_agent() -> None:
    """Run the interactive REPL: read user input, call the model, run tools in a loop.

    Loads API credentials and default model from config, then alternates between
    assistant replies and tool execution until a non-tool response is printed.

    Raises:
        SystemExit: If the configured model id is not found for the account.
    """
    client = ensure_anthropic_client()
    model = ensure_anthropic_model(client.models)
    conversation = [{"role": "system", "content": system_prompt()}]

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
            try:
                assistant_text = call_llm(client, conversation, model)
            except anthropic.NotFoundError as exc:
                raise SystemExit(
                    f"Anthropic model not found: {model!r}. "
                    "Set ANTHROPIC_MODEL to a model available to your account "
                    "or remove it to use the current default "
                    f"'{DEFAULT_MODEL}'."
                ) from exc

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
