"""OpenAI backend, isolated from any other provider's code.

Uses the Responses API, which the current OpenAI docs recommend over the
older Chat Completions API for new text-generation work.
"""

from __future__ import annotations

import os
from pathlib import Path

import openai
from dotenv import load_dotenv
from openai import OpenAI

from agent.providers._shared import choose_model, prompt_api_key, write_env_value
from agent.providers.base import Provider

DEFAULT_MODEL = "gpt-5.5"
FALLBACK_MODELS: list[tuple[str, str]] = [
    ("gpt-5.5", "GPT-5.5"),
    ("gpt-5.4-mini", "GPT-5.4 mini"),
    ("gpt-5.4-nano", "GPT-5.4 nano"),
]

_KEY_LABEL = "OpenAI API key"


def _is_chat_model(model_id: str) -> bool:
    """Return ``True`` for ids that look like chat-style OpenAI models.

    Args:
        model_id: Model id from the OpenAI models list API.

    Returns:
        Whether to include this id in the interactive picker.
    """
    return model_id.startswith(("gpt-", "o1", "o3", "o4", "o5", "chatgpt-"))


def _validate_key(api_key: str) -> OpenAI:
    """Build a client and verify the key with a tiny ``models.list`` call.

    Args:
        api_key: OpenAI API key string.

    Returns:
        Authenticated client after a successful list call.
    """
    client = OpenAI(api_key=api_key)
    next(iter(client.models.list()), None)
    return client


def _ensure_client() -> OpenAI:
    """Load, verify, and persist a working ``OPENAI_API_KEY``.

    Returns:
        Authenticated OpenAI client.

    Raises:
        SystemExit: On empty key, auth failure after retries, or unrecoverable
            connection / API errors.
    """
    env_path = Path.cwd() / ".env"
    load_dotenv(env_path)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    while True:
        if not api_key:
            api_key = prompt_api_key(env_path, "Missing OPENAI_API_KEY.", prompt_label=_KEY_LABEL)

        try:
            client = _validate_key(api_key)
        except openai.AuthenticationError:
            print("OpenAI API key verification failed. Please try again.")
            api_key = prompt_api_key(env_path, "Invalid OPENAI_API_KEY.", prompt_label=_KEY_LABEL)
            continue
        except openai.APIConnectionError as exc:
            detail = str(exc)
            if exc.__cause__:
                detail = f"{detail} ({exc.__cause__})"
            raise SystemExit(
                f"Could not reach OpenAI to verify your API key: {detail}\n\n"
                "This is usually TLS or network trust, not a wrong key. On Windows, common fixes are: "
                "set SSL_CERT_FILE to a PEM bundle that includes your corporate root CA (SSL inspection), "
                "or install https://pypi.org/project/pip-system-certs/ so Python uses the Windows cert store."
            ) from exc
        except openai.APIError as exc:
            raise SystemExit(f"Could not verify OpenAI API key: {exc}") from exc

        write_env_value(env_path, "OPENAI_API_KEY", api_key)
        os.environ["OPENAI_API_KEY"] = api_key
        print(f"Verified OPENAI_API_KEY and saved it to {env_path}.")
        return client


def _list_models(client: OpenAI) -> list[tuple[str, str]]:
    """Return OpenAI chat model ids, falling back to a static list.

    Args:
        client: Authenticated OpenAI client.

    Returns:
        ``(model_id, display_name)`` pairs, or ``FALLBACK_MODELS`` on failure.
    """
    try:
        response = client.models.list()
        models: list[tuple[str, str]] = []
        for model in getattr(response, "data", []):
            model_id = getattr(model, "id", "")
            if model_id and _is_chat_model(model_id):
                models.append((model_id, model_id))
        models.sort(key=lambda pair: pair[0])
        return models or FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS


def _ensure_model(client: OpenAI) -> str:
    """Return ``OPENAI_MODEL`` from env or prompt once and save to ``.env``.

    Args:
        client: Authenticated client used to list models when prompting.

    Returns:
        Model id string to pass to the Responses API.
    """
    env_path = Path.cwd() / ".env"
    load_dotenv(env_path, override=False)

    model = os.getenv("OPENAI_MODEL", "").strip()
    if model:
        return model

    model = choose_model(_list_models(client), label="OpenAI", default_model_id=DEFAULT_MODEL)
    write_env_value(env_path, "OPENAI_MODEL", model)
    os.environ["OPENAI_MODEL"] = model
    print(f"Saved OPENAI_MODEL={model} to {env_path}.")
    return model


class OpenAIProvider(Provider):
    """OpenAI backend using the Responses API."""

    name = "OpenAI"

    def __init__(self, client: OpenAI, model: str) -> None:
        """Wrap a configured client and the chosen model id.

        Args:
            client: Authenticated OpenAI client.
            model: Model id resolved from env or interactive selection.
        """
        self._client = client
        self.model = model

    @classmethod
    def setup(cls) -> "OpenAIProvider":
        """Verify credentials, resolve the model id, and return a ready provider.

        Returns:
            Fully initialized ``OpenAIProvider``.
        """
        client = _ensure_client()
        model = _ensure_model(client)
        return cls(client, model)

    def call(self, conversation: list[dict[str, str]]) -> str:
        """Send the conversation via the Responses API and return assistant text.

        The system prompt is passed as ``instructions``; the remaining turns
        are forwarded as the ``input`` message array. Output is read via
        ``response.output_text`` per current OpenAI guidance.

        Args:
            conversation: First entry is the system prompt; rest is the
                user/assistant transcript.

        Returns:
            Aggregated assistant text, or an empty string when none is returned.

        Raises:
            SystemExit: When the configured model id is not available.
        """
        instructions = conversation[0]["content"]
        input_messages: list[dict[str, str]] = [
            {"role": message["role"], "content": message["content"]}
            for message in conversation[1:]
        ]

        try:
            response = self._client.responses.create(
                model=self.model,
                instructions=instructions,
                input=input_messages,
                max_output_tokens=2000,
            )
        except openai.NotFoundError as exc:
            raise SystemExit(
                f"OpenAI model not found: {self.model!r}. "
                "Set OPENAI_MODEL to a model available to your account "
                f"or remove it to use the current default {DEFAULT_MODEL!r}."
            ) from exc

        return getattr(response, "output_text", "") or ""
