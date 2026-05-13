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

    Unlike the CLI's lenient ``_list_models`` helpers (which silently fall
    back to a hardcoded short list when anything goes wrong), this function
    propagates the real error message so the setup dialog can show the user
    why the list could not be refreshed. The list comes from the provider's
    ``models.list`` endpoint and is fully auto-paginated.

    Args:
        provider_name: Active provider id.
        api_key: Key string to verify with the SDK.

    Returns:
        ``(models, error)``. ``models`` is an empty list on failure;
        ``error`` is empty on success and contains a human-readable reason
        otherwise.
    """
    if provider_name == "anthropic":
        return _fetch_anthropic_models(api_key)
    if provider_name == "openai":
        return _fetch_openai_models(api_key)
    return [], f"Unknown provider: {provider_name!r}"


def _fetch_anthropic_models(api_key: str) -> tuple[list[tuple[str, str]], str]:
    """Validate the key and return every Claude model on the account.

    Iterates the auto-paginating ``client.models.list()`` so accounts with
    more than one page of models still show every entry, not just the first.

    Args:
        api_key: Anthropic API key string.

    Returns:
        ``(models, error)`` tuple as documented on :func:`fetch_live_models`.
    """
    import anthropic

    from agent.providers.anthropic import _validate_key

    try:
        client = _validate_key(api_key)
    except anthropic.AuthenticationError:
        return [], "Anthropic rejected this API key."
    except anthropic.APIConnectionError as exc:
        return [], f"Could not reach Anthropic: {exc}"
    except anthropic.APIError as exc:
        return [], f"Anthropic API error: {exc}"

    try:
        models: list[tuple[str, str]] = []
        for model in client.models.list(limit=1000):
            model_id = getattr(model, "id", "")
            display = getattr(model, "display_name", model_id) or model_id
            if model_id.startswith("claude-"):
                models.append((model_id, display))
    except anthropic.APIError as exc:
        return [], f"Could not list Anthropic models: {exc}"
    except Exception as exc:  # noqa: BLE001 - surface SDK / parsing issues to UI
        return [], f"Could not list Anthropic models: {exc}"

    if not models:
        return [], "Anthropic returned no Claude models for this account."
    return models, ""


def _fetch_openai_models(api_key: str) -> tuple[list[tuple[str, str]], str]:
    """Validate the key and return every chat-capable OpenAI model.

    Iterates the auto-paginating ``client.models.list()`` and applies the
    same ``_is_chat_model`` filter used by the CLI helper, so the dialog
    shows GPT / o-series ids only.

    Args:
        api_key: OpenAI API key string.

    Returns:
        ``(models, error)`` tuple as documented on :func:`fetch_live_models`.
    """
    import openai

    from agent.providers.openai import _is_chat_model, _validate_key

    try:
        client = _validate_key(api_key)
    except openai.AuthenticationError:
        return [], "OpenAI rejected this API key."
    except openai.APIConnectionError as exc:
        return [], f"Could not reach OpenAI: {exc}"
    except openai.APIError as exc:
        return [], f"OpenAI API error: {exc}"

    try:
        models: list[tuple[str, str]] = []
        for model in client.models.list():
            model_id = getattr(model, "id", "")
            if model_id and _is_chat_model(model_id):
                models.append((model_id, model_id))
    except openai.APIError as exc:
        return [], f"Could not list OpenAI models: {exc}"
    except Exception as exc:  # noqa: BLE001 - surface SDK / parsing issues to UI
        return [], f"Could not list OpenAI models: {exc}"

    models.sort(key=lambda pair: pair[0])
    if not models:
        return [], "OpenAI returned no chat-capable models for this account."
    return models, ""


__all__ = [
    "ProviderSetupInfo",
    "fetch_live_models",
    "provider_info",
    "validate_credentials",
]
