from __future__ import annotations

import getpass
import os
from pathlib import Path
from typing import Protocol

import anthropic
from dotenv import load_dotenv

DEFAULT_MODEL = "claude-sonnet-4-6"
FALLBACK_MODELS = [
    ("claude-opus-4-7", "Claude Opus 4.7"),
    ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
    ("claude-haiku-4-5", "Claude Haiku 4.5"),
]


class ModelsClient(Protocol):
    def list(self, **kwargs: object) -> object:
        """List models from the Anthropic API."""
        ...


def write_env_value(env_path: Path, key: str, value: str) -> None:
    """Create or update a single KEY=value entry in a .env file.

    Args:
        env_path: Path to the .env file (created if missing).
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


def prompt_api_key(env_path: Path, reason: str) -> str:
    """Prompt for an Anthropic API key without echoing input.

    Args:
        env_path: .env path that will be mentioned in the prompt text.
        reason: Message printed before the secure password prompt.

    Returns:
        The trimmed API key entered by the user.

    Raises:
        SystemExit: If input is empty or the prompt is cancelled.
    """
    print(reason)
    print(f"I'll create/update {env_path} with the key you enter.")
    try:
        api_key = getpass.getpass("Anthropic API key: ").strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise SystemExit("No API key entered. Exiting.") from exc

    if not api_key:
        raise SystemExit("No API key entered. Exiting.")
    return api_key


def validate_api_key(api_key: str) -> anthropic.Anthropic:
    """Build an Anthropic client and verify the API key with a small request.

    Args:
        api_key: Anthropic API key string.

    Returns:
        Configured client after a successful models list call.
    """
    client = anthropic.Anthropic(api_key=api_key)
    client.models.list(limit=1)
    return client


def ensure_anthropic_client() -> anthropic.Anthropic:
    """Load, verify, and persist a working Anthropic API key.

    Reads ``ANTHROPIC_API_KEY`` from the environment or ``.env``, prompts until
    verification succeeds, then writes the key back to ``.env``.

    Returns:
        Authenticated Anthropic client.

    Raises:
        SystemExit: On empty key, auth failure after retries, connection or API errors.
    """
    env_path = Path.cwd() / ".env"
    load_dotenv(env_path)
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    while True:
        if not api_key:
            api_key = prompt_api_key(env_path, "Missing ANTHROPIC_API_KEY.")

        try:
            client = validate_api_key(api_key)
        except anthropic.AuthenticationError:
            print("Anthropic API key verification failed. Please try again.")
            api_key = prompt_api_key(env_path, "Invalid ANTHROPIC_API_KEY.")
            continue
        except anthropic.APIConnectionError as exc:
            detail = str(exc)
            if exc.__cause__:
                detail = f"{detail} ({exc.__cause__})"
            raise SystemExit(
                f"Could not reach Anthropic to verify your API key: {detail}\n\n"
                "This is usually TLS or network trust, not a wrong key. On Windows, common fixes are: "
                "set SSL_CERT_FILE to a PEM bundle that includes your corporate root CA (SSL inspection), "
                "or install https://pypi.org/project/pip-system-certs/ so Python uses the Windows cert store."
            ) from exc
        except anthropic.APIError as exc:
            raise SystemExit(f"Could not verify Anthropic API key: {exc}") from exc

        write_env_value(env_path, "ANTHROPIC_API_KEY", api_key)
        os.environ["ANTHROPIC_API_KEY"] = api_key
        print(f"Verified ANTHROPIC_API_KEY and saved it to {env_path}.")
        return client


def current_models(models_client: ModelsClient) -> list[tuple[str, str]]:
    """Return Claude model ids and display names, falling back to a static list.

    Args:
        models_client: Client exposing a ``list`` method compatible with Anthropic.

    Returns:
        Pairs of ``(model_id, display_name)`` for Claude models, or
        ``FALLBACK_MODELS`` if the API call fails or returns nothing usable.
    """
    try:
        response = models_client.list(limit=20)
        models = []
        for model in getattr(response, "data", []):
            model_id = getattr(model, "id", "")
            display_name = getattr(model, "display_name", model_id)
            if model_id.startswith("claude-"):
                models.append((model_id, display_name))
        return models or FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS


def choose_model(models: list[tuple[str, str]]) -> str:
    """Prompt the user to pick a default Anthropic model from a numbered list.

    Args:
        models: List of ``(model_id, display_name)`` options.

    Returns:
        Selected ``model_id``.

    Raises:
        SystemExit: If the prompt is cancelled without a selection.
    """
    default_index = next((i for i, (model_id, _) in enumerate(models) if model_id == DEFAULT_MODEL), 0)

    print("\nChoose a default Anthropic model:")
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


def ensure_anthropic_model(models_client: ModelsClient) -> str:
    """Return ``ANTHROPIC_MODEL`` from env or prompt once and save to ``.env``.

    Args:
        models_client: Client used to list models when prompting.

    Returns:
        Model id string to pass to the Messages API.
    """
    env_path = Path.cwd() / ".env"
    load_dotenv(env_path, override=False)

    model = os.getenv("ANTHROPIC_MODEL", "").strip()
    if model:
        return model

    model = choose_model(current_models(models_client))
    write_env_value(env_path, "ANTHROPIC_MODEL", model)
    os.environ["ANTHROPIC_MODEL"] = model
    print(f"Saved ANTHROPIC_MODEL={model} to {env_path}.")
    return model
