"""Template for adding a new LLM backend.

How to use:

1. Copy this file to ``providers/<your_name>.py`` and rename ``TemplateProvider``
   to ``<YourName>Provider``.
2. Replace every ``TODO`` marker (env var names, default model id, fallback
   list, the SDK calls in ``_validate_key`` / ``_list_models`` / ``call``,
   and the vendor-specific exception handlers in ``_ensure_client``).
3. Register the provider in :mod:`agent.providers.__init__`:

   - extend the ``ProviderName`` literal,
   - add a branch in ``resolved_llm_provider`` for the new env value,
   - add a branch in ``build_provider`` returning ``<YourName>Provider.setup()``.

4. Add the SDK to ``pyproject.toml`` dependencies.

This module is intentionally not registered in the factory and importing it
pulls in no vendor SDK; ``TemplateProvider.setup`` and ``.call`` raise
``NotImplementedError`` on purpose.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agent.providers._shared import choose_model, prompt_api_key, write_env_value
from agent.providers.base import Provider

DEFAULT_MODEL = "TODO-default-model-id"
FALLBACK_MODELS: list[tuple[str, str]] = [
    ("TODO-model-id", "TODO display name"),
]

_KEY_LABEL = "TODO vendor API key"
_API_KEY_ENV = "TODO_API_KEY"
_MODEL_ENV = "TODO_MODEL"
_VENDOR_LABEL = "TODO Vendor"


def _validate_key(api_key: str) -> Any:
    """Build the vendor client and verify the key with a minimal request.

    Args:
        api_key: API key string.

    Returns:
        Authenticated vendor client.

    Raises:
        NotImplementedError: This is a template stub; implement using the
            vendor SDK (typically a cheap ``models.list`` call).
    """
    raise NotImplementedError("Implement _validate_key for your vendor SDK.")


def _ensure_client() -> Any:
    """Load, verify, and persist a working API key for this provider.

    Mirrors ``providers/anthropic.py`` / ``providers/openai.py``: read the env
    var, prompt the user until verification passes, then persist back to
    ``.env``. Replace the broad ``except`` with the vendor SDK's specific
    auth / connection / API exception classes.

    Returns:
        Authenticated vendor client.

    Raises:
        SystemExit: On empty key, auth failure after retries, or unrecoverable
            connection / API errors.
    """
    env_path = Path.cwd() / ".env"
    load_dotenv(env_path)
    api_key = os.getenv(_API_KEY_ENV, "").strip()

    while True:
        if not api_key:
            api_key = prompt_api_key(env_path, f"Missing {_API_KEY_ENV}.", prompt_label=_KEY_LABEL)

        try:
            client = _validate_key(api_key)
        except Exception as exc:
            raise SystemExit(f"Could not verify {_KEY_LABEL}: {exc}") from exc

        write_env_value(env_path, _API_KEY_ENV, api_key)
        os.environ[_API_KEY_ENV] = api_key
        print(f"Verified {_API_KEY_ENV} and saved it to {env_path}.")
        return client


def _list_models(client: Any) -> list[tuple[str, str]]:
    """Return model ids and display names, falling back to a static list.

    Args:
        client: Authenticated vendor client.

    Returns:
        ``(model_id, display_name)`` pairs, or ``FALLBACK_MODELS`` on failure.
    """
    return FALLBACK_MODELS


def _ensure_model(client: Any) -> str:
    """Return the configured model id from env or prompt once and save to ``.env``.

    Args:
        client: Authenticated client used to list models when prompting.

    Returns:
        Model id string to pass to the vendor API.
    """
    env_path = Path.cwd() / ".env"
    load_dotenv(env_path, override=False)

    model = os.getenv(_MODEL_ENV, "").strip()
    if model:
        return model

    model = choose_model(_list_models(client), label=_VENDOR_LABEL, default_model_id=DEFAULT_MODEL)
    write_env_value(env_path, _MODEL_ENV, model)
    os.environ[_MODEL_ENV] = model
    print(f"Saved {_MODEL_ENV}={model} to {env_path}.")
    return model


class TemplateProvider(Provider):
    """Template ``Provider`` implementation; rename and fill in TODOs."""

    name = _VENDOR_LABEL

    def __init__(self, client: Any, model: str) -> None:
        """Wrap a configured client and the chosen model id.

        Args:
            client: Authenticated vendor client.
            model: Model id resolved from env or interactive selection.
        """
        self._client = client
        self.model = model

    @classmethod
    def setup(cls) -> "TemplateProvider":
        """Verify credentials, resolve the model id, and return a ready provider.

        Returns:
            Fully initialized ``TemplateProvider``.
        """
        client = _ensure_client()
        model = _ensure_model(client)
        return cls(client, model)

    def call(self, conversation: list[dict[str, str]]) -> str:
        """Send the conversation to the model and return assistant text.

        Implementations typically:

        1. Translate ``conversation`` into the vendor's request shape. The
           runner uses ``conversation[0]`` as the system prompt and the rest
           as ``user`` / ``assistant`` turns (including ``tool_result(...)``
           ``user`` lines).
        2. Call the vendor SDK (for example a ``responses.create`` /
           ``messages.create`` / ``chat.completions.create`` style method).
        3. Extract a single plain-text reply.
        4. Catch the vendor's "model not found" exception and re-raise as
           ``SystemExit`` with a hint that points at ``_MODEL_ENV`` and
           ``DEFAULT_MODEL``.

        Args:
            conversation: First entry is the system prompt; remaining entries
                are the user/assistant transcript.

        Returns:
            Plain text content of the model's reply.

        Raises:
            NotImplementedError: This is a template stub.
            SystemExit: When the configured model id is not available (once
                the real implementation maps the vendor's "not found" error).
        """
        raise NotImplementedError("Implement call() for your vendor SDK.")
