"""Anthropic (Claude) backend, isolated from any other provider's code."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

from agent.providers._shared import choose_model, prompt_api_key, write_env_value
from agent.providers._thinking import (
    ThinkingLevel,
    model_supports_adaptive_thinking,
    resolved_thinking_level,
)
from agent.providers.base import Provider

DEFAULT_MODEL = "claude-sonnet-4-6"
FALLBACK_MODELS: list[tuple[str, str]] = [
    ("claude-opus-4-7", "Claude Opus 4.7"),
    ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
    ("claude-haiku-4-5", "Claude Haiku 4.5"),
]

_KEY_LABEL = "Anthropic API key"

# When thinking is enabled, ``max_tokens`` covers thinking + visible reply, so
# the 2000-token cap used for plain text replies is far too small.
_MAX_TOKENS_DEFAULT = 2000
_MAX_TOKENS_WITH_THINKING = 16000


def _thinking_request_kwargs(
    model_id: str, level: ThinkingLevel | None
) -> dict[str, Any]:
    """Translate the shared thinking level into Messages API kwargs.

    Args:
        model_id: Model that will receive the request. Used to decide whether
            adaptive thinking is even available.
        level: Resolved ``MINI_AGENT_THINKING`` level, or ``None`` for the
            provider's API default.

    Returns:
        Kwargs to splat into ``messages.create``. May be empty when thinking
        is off or unsupported on this model.
    """
    if level == "off":
        return {}
    if not model_supports_adaptive_thinking(model_id):
        return {}
    if level is None:
        return {"thinking": {"type": "adaptive"}}
    return {
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": level},
    }


def _first_text_block(content: list[Any]) -> str:
    """Return the first ``text`` block's content, ignoring any thinking blocks.

    Adaptive thinking responses may start with one or more ``thinking`` blocks
    before the visible reply; ``content[0]`` is therefore not safe to use.

    Args:
        content: ``response.content`` list returned by the Messages API.

    Returns:
        Plain text of the first ``text`` block, or ``str(block)`` of the first
        block when no text block is present (matches the previous behavior).
    """
    for block in content:
        if getattr(block, "type", None) == "text":
            return block.text
    return str(content[0]) if content else ""


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
        response = client.models.list(limit=100)
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

        Extended thinking is configured via ``MINI_AGENT_THINKING``. When
        adaptive thinking is enabled, the response may contain ``thinking``
        blocks before the visible reply; we always return the first ``text``
        block.

        Args:
            conversation: First entry is the system prompt; rest is the
                user/assistant transcript.

        Returns:
            Text content of the first ``text`` block, or ``str(block)`` if no
            text block is present.

        Raises:
            SystemExit: When the configured model id is not available.
        """
        thinking_kwargs = _thinking_request_kwargs(self.model, resolved_thinking_level())
        max_tokens = (
            _MAX_TOKENS_WITH_THINKING if "thinking" in thinking_kwargs else _MAX_TOKENS_DEFAULT
        )
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=conversation[0]["content"],
                messages=conversation[1:],
                **thinking_kwargs,
            )
        except anthropic.NotFoundError as exc:
            raise SystemExit(
                f"Anthropic model not found: {self.model!r}. "
                "Set ANTHROPIC_MODEL to a model available to your account "
                f"or remove it to use the current default {DEFAULT_MODEL!r}."
            ) from exc

        return _first_text_block(response.content)
