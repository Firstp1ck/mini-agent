"""Helpers shared by all provider modules.

These are deliberately provider-agnostic: ``.env`` writing, secure key prompts,
and a numbered model picker. Anything specific to a vendor lives next to that
vendor's provider class instead.
"""

from __future__ import annotations

import getpass
from pathlib import Path


def write_env_value(env_path: Path, key: str, value: str) -> None:
    """Create or update a single ``KEY=value`` entry in a ``.env`` file.

    Args:
        env_path: Path to the ``.env`` file (created if missing).
        key: Environment variable name.
        value: Value to assign (written without extra quoting).
    """
    line = f"{key}={value}\n"
    if not env_path.exists():
        env_path.write_text(line, encoding="utf-8")
        return

    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, existing_line in enumerate(lines):
        stripped = existing_line.lstrip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"export {key}="):
            lines[index] = line
            break
    else:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(line)

    env_path.write_text("".join(lines), encoding="utf-8")


def prompt_api_key(env_path: Path, reason: str, *, prompt_label: str) -> str:
    """Prompt for an API key without echoing input.

    Args:
        env_path: ``.env`` path that will be mentioned in the prompt text.
        reason: Message printed before the secure password prompt.
        prompt_label: Label shown on the password prompt line (for example
            ``"Anthropic API key"``).

    Returns:
        The trimmed API key entered by the user.

    Raises:
        SystemExit: If input is empty or the prompt is cancelled.
    """
    print(reason)
    print(f"I'll create/update {env_path} with the key you enter.")
    try:
        api_key = getpass.getpass(f"{prompt_label}: ").strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise SystemExit("No API key entered. Exiting.") from exc

    if not api_key:
        raise SystemExit("No API key entered. Exiting.")
    return api_key


def choose_model(
    models: list[tuple[str, str]],
    *,
    label: str,
    default_model_id: str,
) -> str:
    """Prompt the user to pick a default model from a numbered list.

    Args:
        models: List of ``(model_id, display_name)`` options.
        label: Provider name printed in the prompt (for example ``"Anthropic"``).
        default_model_id: Model id that receives the ``[default]`` marker when
            present in ``models``.

    Returns:
        Selected ``model_id``.

    Raises:
        SystemExit: If the prompt is cancelled without a selection.
    """
    default_index = next(
        (i for i, (model_id, _) in enumerate(models) if model_id == default_model_id),
        0,
    )

    print(f"\nChoose a default {label} model:")
    for index, (model_id, display_name) in enumerate(models, start=1):
        default_marker = " [default]" if index - 1 == default_index else ""
        print(f"  {index}. {display_name} ({model_id}){default_marker}")

    while True:
        try:
            choice = input(f"Model [default {default_index + 1}]: ").strip()
        except (EOFError, KeyboardInterrupt) as exc:
            raise SystemExit("No model selected. Exiting.") from exc

        if not choice:
            return models[default_index][0]
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice) - 1][0]
        if any(choice == model_id for model_id, _ in models):
            return choice

        print("Enter a number from the list, a model id, or press Enter for the default.")
