"""Unified Tk setup dialog: provider, API key, model, thinking effort.

Shown on GUI startup whenever any of the required values is missing from the
environment. The API key row appears only after the user picks a provider.
The model dropdown is seeded with the provider's hardcoded fallback list and
is refreshed with the live list returned by the provider's ``models.list``
API as soon as a usable API key is available (either prefilled from ``.env``
or entered by the user).
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import tkinter as tk

from agent.gui._setup_providers import (
    ProviderSetupInfo,
    fetch_live_models,
    provider_info,
    validate_credentials,
)
from agent.gui._setup_style import (
    SHELL_BG,
    apply_setup_style,
    make_card,
    make_field_combo,
    make_field_entry,
    make_field_label,
    make_primary_button,
    make_secondary_button,
    make_status_label,
)
from agent.providers import AVAILABLE_PROVIDERS, ProviderName
from agent.providers._shared import write_env_value
from agent.providers._thinking import (
    SETUP_THINKING_MENU,
    VALID_LEVELS,
    filter_thinking_menu,
)


@dataclass(frozen=True)
class SetupResult:
    """Values chosen in the setup dialog, ready to persist to ``.env``.

    Attributes:
        provider: Selected provider id (``"anthropic"`` or ``"openai"``).
        api_key: Verified API key for that provider.
        model: Model id (for example ``"claude-sonnet-4-6"``).
        thinking: One of :data:`agent.providers._thinking.VALID_LEVELS` or
            ``"auto"``.
    """

    provider: ProviderName
    api_key: str
    model: str
    thinking: str


def setup_needs_prompt() -> bool:
    """Return ``True`` if any required env var is missing for the current setup.

    Required values are: ``MINI_AGENT_PROVIDER`` (and a valid id), the matching
    ``<PROVIDER>_API_KEY`` and ``<PROVIDER>_MODEL`` for that provider, and
    ``MINI_AGENT_THINKING``. The dialog is also shown when the env value is
    set to something unsupported, so the user can fix it without editing
    ``.env`` by hand.

    Returns:
        Whether the GUI should open the setup dialog before starting.
    """
    raw_provider = os.getenv("MINI_AGENT_PROVIDER", "").strip().lower()
    known = {name for name, _ in AVAILABLE_PROVIDERS}
    if raw_provider not in known:
        return True
    info = provider_info(cast(ProviderName, raw_provider))
    if not os.getenv(info.api_key_env, "").strip():
        return True
    if not os.getenv(info.model_env, "").strip():
        return True
    thinking = os.getenv("MINI_AGENT_THINKING", "").strip().lower()
    if not thinking:
        return True
    if thinking != "auto" and thinking not in VALID_LEVELS:
        return True
    return False


def apply_setup_result(result: SetupResult) -> None:
    """Persist ``result`` to ``.env`` and the process environment.

    Args:
        result: Values returned by :func:`run_setup_dialog`.
    """
    env_path = Path.cwd() / ".env"
    info = provider_info(result.provider)

    write_env_value(env_path, "MINI_AGENT_PROVIDER", result.provider)
    os.environ["MINI_AGENT_PROVIDER"] = result.provider

    write_env_value(env_path, info.api_key_env, result.api_key)
    os.environ[info.api_key_env] = result.api_key

    write_env_value(env_path, info.model_env, result.model)
    os.environ[info.model_env] = result.model

    write_env_value(env_path, "MINI_AGENT_THINKING", result.thinking)
    os.environ["MINI_AGENT_THINKING"] = result.thinking


def _build_setup_widgets(dialog: tk.Toplevel) -> dict[str, Any]:
    """Lay out the dialog widgets and return a handle dict.

    The API key row (label + entry) is created but not gridded; the caller's
    provider-change handler grids it once a provider is picked.

    Args:
        dialog: Toplevel that will host the form.

    Returns:
        Mapping of widget/variable names to instances. Keys: ``provider_var``,
        ``provider_combo``, ``api_label``, ``api_entry``, ``api_var``,
        ``model_var``, ``model_combo``, ``thinking_var``, ``thinking_combo``,
        ``status_var``, ``ok_btn``, ``cancel_btn``.
    """
    apply_setup_style(dialog)
    dialog.configure(bg=SHELL_BG)

    outer = tk.Frame(dialog, bg=SHELL_BG, padx=18, pady=18)
    outer.pack(fill="both", expand=True)
    card = make_card(outer)
    card.pack(fill="both", expand=True, ipadx=18, ipady=18)

    provider_var = tk.StringVar()
    model_var = tk.StringVar()
    api_var = tk.StringVar()
    thinking_var = tk.StringVar()
    status_var = tk.StringVar(value="")

    make_field_label(card, "Provider:").grid(row=0, column=0, sticky="w", pady=6, padx=(16, 12))
    provider_combo = make_field_combo(card, provider_var)
    provider_combo.configure(values=[label for _, label in AVAILABLE_PROVIDERS], state="readonly")
    provider_combo.grid(row=0, column=1, sticky="ew", pady=6, padx=(0, 16))

    make_field_label(card, "Model:").grid(row=1, column=0, sticky="w", pady=6, padx=(16, 12))
    model_combo = make_field_combo(card, model_var)
    model_combo.grid(row=1, column=1, sticky="ew", pady=6, padx=(0, 16))

    make_field_label(card, "Thinking:").grid(row=2, column=0, sticky="w", pady=6, padx=(16, 12))
    thinking_combo = make_field_combo(card, thinking_var)
    thinking_combo.grid(row=2, column=1, sticky="ew", pady=6, padx=(0, 16))

    api_label = make_field_label(card, "API key:")
    api_entry = make_field_entry(card, api_var, show="•")

    status_label = make_status_label(card, status_var)
    status_label.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0), padx=16)

    button_row = tk.Frame(card, bg=card["bg"])
    button_row.grid(row=5, column=0, columnspan=2, pady=(16, 0), padx=16, sticky="e")
    ok_btn = make_primary_button(button_row, "OK")
    cancel_btn = make_secondary_button(button_row, "Cancel")
    cancel_btn.pack(side="right", padx=(8, 0))
    ok_btn.pack(side="right")

    return {
        "card": card,
        "provider_var": provider_var,
        "provider_combo": provider_combo,
        "api_label": api_label,
        "api_entry": api_entry,
        "api_var": api_var,
        "model_var": model_var,
        "model_combo": model_combo,
        "thinking_var": thinking_var,
        "thinking_combo": thinking_combo,
        "status_var": status_var,
        "ok_btn": ok_btn,
        "cancel_btn": cancel_btn,
    }


def _thinking_menu_for(provider_id: ProviderName, model_id: str) -> list[tuple[str, str]]:
    """Return the thinking menu filtered to what this provider+model accepts.

    Falls back to the full :data:`SETUP_THINKING_MENU` if the filter returns
    nothing (defensive — should never happen in practice).

    Args:
        provider_id: Resolved provider id.
        model_id: Selected model id (may be empty if the user hasn't chosen).

    Returns:
        Ordered ``(value, label)`` pairs for the dropdown.
    """
    if not model_id:
        return list(SETUP_THINKING_MENU)
    menu = filter_thinking_menu(provider_id, model_id)
    return menu or list(SETUP_THINKING_MENU)


def _thinking_display_entry(menu: list[tuple[str, str]], value: str) -> str:
    """Return the combobox display string for ``value``, or pick the default.

    The display is just the bare level name (for example ``"auto"`` or
    ``"medium"``) so the dropdown stays scannable.

    Args:
        menu: Available ``(value, label)`` entries from :func:`_thinking_menu_for`.
        value: Preferred value (typically from ``MINI_AGENT_THINKING``).

    Returns:
        ``value`` when it appears in ``menu``; otherwise the first menu entry's
        value.
    """
    for v, _label in menu:
        if v == value:
            return v
    return menu[0][0]


def _model_dropdown_values(info: ProviderSetupInfo) -> list[str]:
    """Return the fallback model ids as combobox entries.

    The display string is the bare model identifier (for example
    ``"gpt-5.5"``). Providers like OpenAI use the same string for id and
    display name, so an ``"id — name"`` form just duplicated the text.

    Args:
        info: Provider setup metadata.

    Returns:
        Ordered model id strings for the chosen provider.
    """
    return [mid for mid, _ in info.fallback_models]


def _select_initial_model(info: ProviderSetupInfo, values: list[str]) -> str:
    """Pick the model entry that matches env or the provider's default.

    Args:
        info: Provider setup metadata.
        values: ``_model_dropdown_values`` for the provider.

    Returns:
        The combobox display string to preselect, or ``""`` if the fallback
        list is empty.
    """
    stored = os.getenv(info.model_env, "").strip() or info.default_model
    if stored in values:
        return stored
    return values[0] if values else ""


class _SetupController:
    """Glue between the dialog widgets and the validate/submit lifecycle.

    Lives only for the duration of one :func:`run_setup_dialog` call. Splits
    the dialog logic into small methods so the public entry function stays
    short and the handlers can share widget/state references cleanly.
    """

    def __init__(self, dialog: tk.Toplevel, widgets: dict[str, Any]) -> None:
        """Wire up handlers and seed the dialog with values from ``.env``.

        Args:
            dialog: Toplevel returned by :func:`_build_setup_widgets`' caller.
            widgets: Widget/variable handles from :func:`_build_setup_widgets`.
        """
        self._dialog = dialog
        self._widgets = widgets
        self._result: SetupResult | None = None
        self._label_to_id: dict[str, ProviderName] = {
            label: pid for pid, label in AVAILABLE_PROVIDERS
        }
        # (provider, key) tuple of the most recent successful live model fetch,
        # used to avoid re-querying the API on every focus change.
        self._last_models_fetch: tuple[ProviderName, str] | None = None

        widgets["provider_combo"].bind("<<ComboboxSelected>>", self._on_provider_change)
        widgets["model_combo"].bind("<<ComboboxSelected>>", self._on_model_change)
        widgets["api_entry"].bind("<FocusOut>", self._on_api_key_blur)
        widgets["ok_btn"].configure(command=self._attempt_submit)
        widgets["cancel_btn"].configure(command=self._cancel)
        dialog.protocol("WM_DELETE_WINDOW", self._cancel)
        dialog.bind("<Return>", lambda _e: self._attempt_submit())
        dialog.bind("<Escape>", lambda _e: self._cancel())

        initial_provider = os.getenv("MINI_AGENT_PROVIDER", "").strip().lower()
        for pid, label in AVAILABLE_PROVIDERS:
            if pid == initial_provider:
                widgets["provider_var"].set(label)
                self._on_provider_change()
                break

    @property
    def result(self) -> SetupResult | None:
        """Return what the user picked, or ``None`` if they cancelled."""
        return self._result

    def _show_api_row(self, info: ProviderSetupInfo) -> None:
        """Reveal the API key row and prefill it from ``.env`` if present."""
        self._widgets["api_label"].configure(text=f"{info.key_label}:")
        self._widgets["api_label"].grid(row=3, column=0, sticky="w", pady=6, padx=(16, 12))
        self._widgets["api_entry"].grid(row=3, column=1, sticky="ew", pady=6, padx=(0, 16), ipady=6)
        self._widgets["api_var"].set(os.getenv(info.api_key_env, "").strip())

    def _on_provider_change(self, _event: object = None) -> None:
        """Populate the model list, reveal the API key row, and refresh thinking."""
        pid = self._label_to_id.get(self._widgets["provider_var"].get())
        if pid is None:
            return
        info = provider_info(pid)
        self._show_api_row(info)
        values = _model_dropdown_values(info)
        self._widgets["model_combo"].configure(values=values, state="readonly")
        self._widgets["model_var"].set(_select_initial_model(info, values))
        self._refresh_thinking_dropdown(pid)
        self._widgets["status_var"].set("")
        self._last_models_fetch = None
        self._maybe_refresh_models()

    def _on_model_change(self, _event: object = None) -> None:
        """Recompute the thinking dropdown when the user picks a different model."""
        pid = self._label_to_id.get(self._widgets["provider_var"].get())
        if pid is None:
            return
        self._refresh_thinking_dropdown(pid)

    def _on_api_key_blur(self, _event: object = None) -> None:
        """Refresh the live model list when the API key field loses focus."""
        self._maybe_refresh_models()

    def _maybe_refresh_models(self) -> None:
        """Start a live model fetch if provider + non-empty key changed since last."""
        pid = self._label_to_id.get(self._widgets["provider_var"].get())
        if pid is None:
            return
        api_key = self._widgets["api_var"].get().strip()
        if not api_key:
            return
        if self._last_models_fetch == (pid, api_key):
            return
        self._widgets["status_var"].set("Loading available models…")
        threading.Thread(
            target=self._models_fetch_worker,
            args=(pid, api_key),
            daemon=True,
        ).start()

    def _models_fetch_worker(self, pid: ProviderName, api_key: str) -> None:
        """Call :func:`fetch_live_models` off-thread and post the result back."""
        models, error = fetch_live_models(pid, api_key)
        self._dialog.after(
            0, lambda: self._on_models_fetched(pid, api_key, models, error)
        )

    def _on_models_fetched(
        self,
        pid: ProviderName,
        api_key: str,
        models: list[tuple[str, str]],
        error: str,
    ) -> None:
        """Apply the fetched live model list to the dropdown on the Tk thread.

        Stale results (provider or key changed while the fetch was in flight)
        are ignored. Failed fetches are silent — the fallback list stays in
        place and the user can still submit; the final OK click re-validates
        the key and surfaces any error there.

        Args:
            pid: Provider id the fetch was started for.
            api_key: Key the fetch was started with.
            models: ``(id, display_name)`` pairs returned by the SDK.
            error: Error message, or ``""`` on success.
        """
        current_pid = self._label_to_id.get(self._widgets["provider_var"].get())
        current_key = self._widgets["api_var"].get().strip()
        if pid != current_pid or api_key != current_key:
            return
        if self._widgets["status_var"].get() == "Loading available models…":
            self._widgets["status_var"].set("")
        if error or not models:
            return
        self._last_models_fetch = (pid, api_key)
        info = provider_info(pid)
        values = [mid for mid, _ in models]
        current_entry = self._widgets["model_var"].get()
        self._widgets["model_combo"].configure(values=values, state="readonly")
        if current_entry in values:
            self._widgets["model_var"].set(current_entry)
        else:
            self._widgets["model_var"].set(_select_initial_model(info, values))
        self._refresh_thinking_dropdown(pid)

    def _refresh_thinking_dropdown(self, pid: ProviderName) -> None:
        """Rebuild the thinking dropdown for the currently-selected model.

        Preserves the user's previous choice when the new model still
        supports it; otherwise falls back to the stored env value, or the
        first entry of the filtered menu.

        Args:
            pid: Active provider id.
        """
        model_id = self._widgets["model_var"].get().strip()
        menu = _thinking_menu_for(pid, model_id)
        previous = self._widgets["thinking_var"].get().strip().lower()
        allowed = {value for value, _ in menu}
        preferred = previous if previous in allowed else (
            os.getenv("MINI_AGENT_THINKING", "").strip().lower() or menu[0][0]
        )
        self._widgets["thinking_combo"].configure(
            values=[value for value, _ in menu],
            state="readonly",
        )
        self._widgets["thinking_var"].set(_thinking_display_entry(menu, preferred))

    def _set_form_state(self, enabled: bool) -> None:
        """Enable or disable all interactive widgets during validation."""
        combo_state = "readonly" if enabled else "disabled"
        model_combo = self._widgets["model_combo"]
        thinking_combo = self._widgets["thinking_combo"]
        self._widgets["provider_combo"].configure(state=combo_state)
        model_combo.configure(state=combo_state if model_combo.cget("values") else "disabled")
        thinking_combo.configure(state=combo_state if thinking_combo.cget("values") else "disabled")
        self._widgets["api_entry"].configure(state="normal" if enabled else "disabled")
        self._widgets["ok_btn"].configure(state="normal" if enabled else "disabled")
        self._widgets["cancel_btn"].configure(state="normal" if enabled else "disabled")

    def _collect_inputs(self) -> tuple[ProviderName, str, str, str] | None:
        """Read and validate field values; return ``None`` and set status on error."""
        pid = self._label_to_id.get(self._widgets["provider_var"].get())
        if pid is None:
            self._widgets["status_var"].set("Please choose a provider.")
            return None
        api_key = self._widgets["api_var"].get().strip()
        if not api_key:
            self._widgets["status_var"].set("Please enter an API key.")
            return None
        model_entry = self._widgets["model_var"].get().strip()
        if not model_entry:
            self._widgets["status_var"].set("Please choose a model.")
            return None
        thinking_entry = self._widgets["thinking_var"].get().strip()
        if not thinking_entry:
            self._widgets["status_var"].set("Please choose a thinking level.")
            return None
        return (pid, api_key, model_entry, thinking_entry)

    def _attempt_submit(self) -> None:
        """Collect inputs and verify the API key on a worker thread."""
        collected = self._collect_inputs()
        if collected is None:
            return
        pid, api_key, model_id, thinking_id = collected

        self._set_form_state(False)
        self._widgets["status_var"].set(f"Verifying {pid.title()} API key…")
        threading.Thread(
            target=self._validate_worker,
            args=(pid, api_key, model_id, thinking_id),
            daemon=True,
        ).start()

    def _validate_worker(
        self, pid: ProviderName, api_key: str, model_id: str, thinking_id: str
    ) -> None:
        """Run :func:`validate_credentials` off-thread and post the result back."""
        error = validate_credentials(pid, api_key)
        self._dialog.after(
            0, lambda: self._on_validate_done(pid, api_key, model_id, thinking_id, error)
        )

    def _on_validate_done(
        self,
        pid: ProviderName,
        api_key: str,
        model_id: str,
        thinking_id: str,
        error: str,
    ) -> None:
        """Apply the validation outcome on the Tk main thread."""
        if error:
            self._widgets["status_var"].set(error)
            self._set_form_state(True)
            return
        self._result = SetupResult(
            provider=pid,
            api_key=api_key,
            model=model_id,
            thinking=thinking_id,
        )
        self._dialog.destroy()

    def _cancel(self) -> None:
        """Close the dialog without saving anything."""
        self._result = None
        self._dialog.destroy()


def run_setup_dialog(root: tk.Tk) -> SetupResult | None:
    """Show the unified Tk setup dialog. Returns choices or ``None`` on cancel.

    The dialog must be invoked on the Tk main thread. The API key field
    appears once a provider is selected; the model dropdown starts with the
    provider's hardcoded fallback list and is replaced with the live list
    from the vendor's ``models.list`` endpoint as soon as a usable API key
    is available (either prefilled from ``.env`` or entered into the entry).
    OK re-validates the API key against the vendor API before returning.

    Args:
        root: Tk root used as the dialog parent.

    Returns:
        :class:`SetupResult` with verified values, or ``None`` if the user
        cancels or closes the dialog.
    """
    dialog = tk.Toplevel(root)
    dialog.title("mini-agent setup")
    dialog.transient(root)
    dialog.resizable(False, False)
    dialog.grab_set()

    widgets = _build_setup_widgets(dialog)
    controller = _SetupController(dialog, widgets)
    widgets["provider_combo"].focus_set()
    root.wait_window(dialog)
    return controller.result
