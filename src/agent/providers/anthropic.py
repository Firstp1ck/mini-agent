"""Anthropic (Claude) backend, isolated from any other provider's code."""

from __future__ import annotations

import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from agent.providers._shared import choose_model, prompt_api_key, write_env_value
from agent.providers.base import Provider

DEFAULT_MODEL = "claude-sonnet-4-6"
FALLBACK_MODELS: list[tuple[str, str]] = [
    ("claude-opus-4-7", "Claude Opus 4.7"),
    ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
    ("claude-haiku-4-5", "Claude Haiku 4.5"),
]

_KEY_LABEL = "Anthropic API key"


def _validate_key(api_key: str) -> anthropic.Anthropic:
    """Build a client and verify the key with a tiny ``models.list`` call.

    Args:
        api_key: Anthropic API key string.

    Returns:
        Authenticated client after a successful list call.
    """
    client = anthropic.Anthropic(api_key=api_key)
    client.models.list(limit=1)
    return client


def _ensure_client() -> anthropic.Anthropic:
    """Load, verify, and persist a working ``ANTHROPIC_API_KEY``.

    Returns:
        Authenticated Anthropic client.

    Raises:
        SystemExit: On empty key, auth failure after retries, or unrecoverable
            connection / API errors.
    """
    env_path = Path.cwd() / ".env"
    load_dotenv(env_path)
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    while True:
        if not api_key:
            api_key = prompt_api_key(env_path, "Missing ANTHROPIC_API_KEY.", prompt_label=_KEY_LABEL)

        try:
            client = _validate_key(api_key)
        except anthropic.AuthenticationError:
            print("Anthropic API key verification failed. Please try again.")
            api_key = prompt_api_key(env_path, "Invalid ANTHROPIC_API_KEY.", prompt_label=_KEY_LABEL)
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


def _list_models(client: anthropic.Anthropic) -> list[tuple[str, str]]:
    """Return Claude model ids and display names, falling back to a static list.

    Args:
        client: Authenticated Anthropic client.

    Returns:
        ``(model_id, display_name)`` pairs, or ``FALLBACK_MODELS`` on failure.
    """
    try:
        response = client.models.list(limit=20)
        models: list[tuple[str, str]] = []
        for model in getattr(response, "data", []):
            model_id = getattr(model, "id", "")
            display_name = getattr(model, "display_name", model_id)
            if model_id.startswith("claude-"):
                models.append((model_id, display_name))
        return models or FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS


def _ensure_model(client: anthropic.Anthropic) -> str:
    """Return ``ANTHROPIC_MODEL`` from env or prompt once and save to ``.env``.

    Args:
        client: Authenticated client used to list models when prompting.

    Returns:
        Model id string to pass to the Messages API.
    """
    env_path = Path.cwd() / ".env"
    load_dotenv(env_path, override=False)

    model = os.getenv("ANTHROPIC_MODEL", "").strip()
    if model:
        return model

    model = choose_model(_list_models(client), label="Anthropic", default_model_id=DEFAULT_MODEL)
    write_env_value(env_path, "ANTHROPIC_MODEL", model)
    os.environ["ANTHROPIC_MODEL"] = model
    print(f"Saved ANTHROPIC_MODEL={model} to {env_path}.")
    return model


class AnthropicProvider(Provider):
    """Claude backend using the Messages API."""

    name = "Anthropic"

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        """Wrap a configured client and the chosen model id.

        Args:
            client: Authenticated Anthropic client.
            model: Model id resolved from env or interactive selection.
        """
        self._client = client
        self.model = model

    @classmethod
    def setup(cls) -> "AnthropicProvider":
        """Verify credentials, resolve the model id, and return a ready provider.

        Returns:
            Fully initialized ``AnthropicProvider``.
        """
        client = _ensure_client()
        model = _ensure_model(client)
        return cls(client, model)

    def call(self, conversation: list[dict[str, str]]) -> str:
        """Send the conversation to Claude and return the assistant text.

        Args:
            conversation: First entry is the system prompt; rest is the
                user/assistant transcript.

        Returns:
            Text content of the first response block, or ``str(block)`` if
            the block is not plain text.

        Raises:
            SystemExit: When the configured model id is not available.
        """
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=conversation[0]["content"],
                messages=conversation[1:],
            )
        except anthropic.NotFoundError as exc:
            raise SystemExit(
                f"Anthropic model not found: {self.model!r}. "
                "Set ANTHROPIC_MODEL to a model available to your account "
                f"or remove it to use the current default {DEFAULT_MODEL!r}."
            ) from exc

        block = response.content[0]
        return block.text if block.type == "text" else str(block)
