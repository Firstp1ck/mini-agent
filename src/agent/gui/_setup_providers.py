"""Provider-specific helpers used by the unified GUI setup dialog.

Kept in its own module so :mod:`agent.gui.setup_dialog` stays focused on Tk
widget layout and the controller lifecycle. Everything here is provider
plumbing: env-var names, fallback model lists, API key validation, and the
live model fetcher.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent.providers import ProviderName


@dataclass(frozen=True)
class ProviderSetupInfo:
    """Per-provider details needed to drive the dialog and write env vars.

    Attributes:
        api_key_env: Env var that stores this provider's API key.
        model_env: Env var that stores the selected model id.
        default_model: Model id to preselect when nothing is stored.
        fallback_models: Static ``(id, display_name)`` list used until the
            live list arrives from the SDK.
        key_label: Human-readable label for the API key field.
    """

    api_key_env: str
    model_env: str
    default_model: str
    fallback_models: list[tuple[str, str]]
    key_label: str


def provider_info(provider_name: ProviderName) -> ProviderSetupInfo:
    """Return env-var names, default model, fallback list, and key label.

    The provider SDK module is imported lazily so picking one provider does
    not force loading the other vendor's SDK.

    Args:
        provider_name: Validated provider id.

    Returns:
        Setup metadata used by the dialog widgets and the env-var writer.
    """
    if provider_name == "anthropic":
        from agent.providers.anthropic import DEFAULT_MODEL, FALLBACK_MODELS

        return ProviderSetupInfo(
            api_key_env="ANTHROPIC_API_KEY",
            model_env="ANTHROPIC_MODEL",
            default_model=DEFAULT_MODEL,
            fallback_models=FALLBACK_MODELS,
            key_label="Anthropic API key",
        )
    if provider_name == "openai":
        from agent.providers.openai import DEFAULT_MODEL, FALLBACK_MODELS

        return ProviderSetupInfo(
            api_key_env="OPENAI_API_KEY",
            model_env="OPENAI_MODEL",
            default_model=DEFAULT_MODEL,
            fallback_models=FALLBACK_MODELS,
            key_label="OpenAI API key",
        )
    raise ValueError(f"Unknown provider: {provider_name!r}")


def validate_credentials(provider_name: ProviderName, api_key: str) -> str:
    """Verify ``api_key`` with a tiny SDK call. Returns ``""`` on success.

    Args:
        provider_name: Active provider id.
        api_key: Key string entered by the user.

    Returns:
        Empty string on success, otherwise a human-readable error message
        suitable for showing inline in the dialog.
    """
    if provider_name == "anthropic":
        import anthropic

        from agent.providers.anthropic import _validate_key

        try:
            _validate_key(api_key)
            return ""
        except anthropic.AuthenticationError:
            return "Anthropic rejected this API key. Double-check and try again."
        except anthropic.APIConnectionError as exc:
            return f"Could not reach Anthropic: {exc}"
        except anthropic.APIError as exc:
            return f"Anthropic API error: {exc}"

    if provider_name == "openai":
        import openai

        from agent.providers.openai import _validate_key

        try:
            _validate_key(api_key)
            return ""
        except openai.AuthenticationError:
            return "OpenAI rejected this API key. Double-check and try again."
        except openai.APIConnectionError as exc:
            return f"Could not reach OpenAI: {exc}"
        except openai.APIError as exc:
            return f"OpenAI API error: {exc}"

    return f"Unknown provider: {provider_name!r}"


def fetch_live_models(
    provider_name: ProviderName, api_key: str
) -> tuple[list[tuple[str, str]], str]:
    """Verify ``api_key`` and return the provider's full model list.

    Both calls run on the calling thread; invoke this from a worker so the Tk
    main loop stays responsive. The list comes from the provider's
    ``models.list`` endpoint (Anthropic up to 100; OpenAI returns all chat
    models, filtered to GPT/o-series ids).

    Args:
        provider_name: Active provider id.
        api_key: Key string to verify with the SDK.

    Returns:
        ``(models, error)``. ``models`` is an empty list on failure;
        ``error`` is empty on success.
    """
    if provider_name == "anthropic":
        import anthropic

        from agent.providers.anthropic import _list_models, _validate_key

        try:
            client = _validate_key(api_key)
        except anthropic.AuthenticationError:
            return [], "Anthropic rejected this API key."
        except anthropic.APIConnectionError as exc:
            return [], f"Could not reach Anthropic: {exc}"
        except anthropic.APIError as exc:
            return [], f"Anthropic API error: {exc}"
        return _list_models(client), ""

    if provider_name == "openai":
        import openai

        from agent.providers.openai import _list_models, _validate_key

        try:
            client = _validate_key(api_key)
        except openai.AuthenticationError:
            return [], "OpenAI rejected this API key."
        except openai.APIConnectionError as exc:
            return [], f"Could not reach OpenAI: {exc}"
        except openai.APIError as exc:
            return [], f"OpenAI API error: {exc}"
        return _list_models(client), ""

    return [], f"Unknown provider: {provider_name!r}"


__all__ = [
    "ProviderSetupInfo",
    "fetch_live_models",
    "provider_info",
    "validate_credentials",
]
