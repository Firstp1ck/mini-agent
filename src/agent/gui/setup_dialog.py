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

from agent.gui._setup_layout import (
    build_setup_widgets,
    model_dropdown_values,
    select_initial_model,
    thinking_display_entry,
    thinking_menu_for,
)
from agent.gui._setup_providers import (
    ProviderSetupInfo,
    fetch_live_models,
    provider_info,
    validate_credentials,
)
from agent.gui.theme import DANGER, MUTED, SUCCESS
from agent.providers import AVAILABLE_PROVIDERS, ProviderName
from agent.providers._shared import write_env_value
from agent.providers._thinking import VALID_LEVELS


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


class _SetupController:
    """Glue between the dialog widgets and the validate/submit lifecycle.

    Lives only for the duration of one :func:`run_setup_dialog` call. Splits
    the dialog logic into small methods so the public entry function stays
    short and the handlers can share widget/state references cleanly.
    """

    def __init__(self, dialog: tk.Toplevel, widgets: dict[str, Any]) -> None:
        """Wire up handlers and seed the dialog with values from ``.env``.

        Args:
            dialog: Toplevel returned by :func:`build_setup_widgets`' caller.
            widgets: Widget/variable handles from :func:`build_setup_widgets`.
        """
        self._dialog = dialog
        self._widgets = widgets
        self._result: SetupResult | None = None
        self._label_to_id: dict[str, ProviderName] = {
            label: pid for pid, label in AVAILABLE_PROVIDERS
        }
        # (provider, key) tuple of the most recent successful live model fetch,
        # used to avoid re-querying the API on every keystroke / focus change.
        self._last_models_fetch: tuple[ProviderName, str] | None = None
        # ``after`` id of a pending debounced model fetch, or ``None`` when
        # idle. Cancelled and re-scheduled on every keystroke / paste in the
        # API key entry so we only hit the network once the user pauses.
        self._api_debounce_id: str | None = None

        widgets["provider_combo"].bind("<<ComboboxSelected>>", self._on_provider_change)
        widgets["model_combo"].bind("<<ComboboxSelected>>", self._on_model_change)
        widgets["api_entry"].bind("<FocusOut>", self._on_api_key_blur)
        widgets["api_var"].trace_add("write", lambda *_: self._on_api_key_typed())
        widgets["verify_btn"].configure(command=self._on_verify_clicked)
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
        """Reveal the API key row, hint, and Verify button; prefill from ``.env``.

        Args:
            info: Provider setup metadata used to label the key field and to
                locate the matching env var to prefill.
        """
        self._widgets["api_label"].configure(text=f"{info.key_label}:")
        self._widgets["api_label"].grid(row=3, column=0, sticky="w", pady=6, padx=(16, 12))
        self._widgets["api_row"].grid(row=3, column=1, sticky="ew", pady=6, padx=(0, 16))
        self._widgets["api_hint"].grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(0, 6), padx=16
        )
        self._widgets["api_var"].set(os.getenv(info.api_key_env, "").strip())

    def _on_provider_change(self, _event: object = None) -> None:
        """Populate the model list, reveal the API key row, and refresh thinking."""
        pid = self._label_to_id.get(self._widgets["provider_var"].get())
        if pid is None:
            return
        info = provider_info(pid)
        self._show_api_row(info)
        values = model_dropdown_values(info)
        self._widgets["model_combo"].configure(values=values, state="readonly")
        self._widgets["model_var"].set(select_initial_model(info, values))
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
        """Fire any pending debounced fetch immediately when the entry loses focus."""
        self._cancel_api_debounce()
        self._maybe_refresh_models()

    def _on_api_key_typed(self) -> None:
        """Schedule a debounced live model fetch after the user pauses typing.

        Bound to the ``api_var`` ``write`` trace so it also covers paste,
        ``set()`` from :meth:`_show_api_row`, and any other programmatic
        change. The 600ms window keeps us off the network during a fast
        paste of a long key, but feels instant after the user stops typing.
        Any previously shown verify indicator is cleared because the key
        the user typed now no longer matches what was last verified.
        """
        self._set_verify_indicator("clear")
        self._cancel_api_debounce()
        self._api_debounce_id = self._dialog.after(600, self._fire_debounced_fetch)

    def _cancel_api_debounce(self) -> None:
        """Cancel a pending debounced fetch if one is queued."""
        if self._api_debounce_id is not None:
            self._dialog.after_cancel(self._api_debounce_id)
            self._api_debounce_id = None

    def _fire_debounced_fetch(self) -> None:
        """Tk ``after`` callback that runs the debounced model fetch."""
        self._api_debounce_id = None
        self._maybe_refresh_models()

    def _on_verify_clicked(self) -> None:
        """Verify the API key right now and reload the model list.

        Bypasses the typing debounce and the ``_last_models_fetch`` cache so
        the request runs even when the field has not changed since the last
        successful fetch. Surfaces an inline status message if the form is
        not ready (missing provider or empty key). The ✓/✗ indicator next
        to the button is cleared until the fetch returns.
        """
        self._cancel_api_debounce()
        self._set_verify_indicator("clear")
        pid = self._label_to_id.get(self._widgets["provider_var"].get())
        if pid is None:
            self._widgets["status_var"].set("Please choose a provider first.")
            return
        if not self._widgets["api_var"].get().strip():
            self._widgets["status_var"].set("Please enter an API key first.")
            return
        self._last_models_fetch = None
        self._maybe_refresh_models()

    def _set_verify_indicator(self, state: str) -> None:
        """Update the small ✓/✗ marker next to the Verify button.

        Args:
            state: ``"ok"`` for a green check, ``"fail"`` for a red cross, or
                any other value (typically ``""`` or ``"clear"``) to hide it.
        """
        var = self._widgets["verify_status_var"]
        indicator = self._widgets["verify_indicator"]
        if state == "ok":
            var.set("\u2713")
            indicator.configure(fg=SUCCESS)
        elif state == "fail":
            var.set("\u2717")
            indicator.configure(fg=DANGER)
        else:
            var.set("")
            indicator.configure(fg=MUTED)

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
        are ignored. When the fetch fails, the error is shown in the dialog
        status line so the user can see why the dropdown still holds the
        fallback list (e.g. a network/SSL problem or a permissions issue
        with the vendor's ``/models`` endpoint).

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
        if error:
            self._widgets["status_var"].set(error)
            self._set_verify_indicator("fail")
            return
        if not models:
            if self._widgets["status_var"].get() == "Loading available models…":
                self._widgets["status_var"].set("")
            self._set_verify_indicator("fail")
            return
        if self._widgets["status_var"].get() == "Loading available models…":
            self._widgets["status_var"].set("")
        self._set_verify_indicator("ok")
        self._last_models_fetch = (pid, api_key)
        info = provider_info(pid)
        values = [mid for mid, _ in models]
        current_entry = self._widgets["model_var"].get()
        self._widgets["model_combo"].configure(values=values, state="readonly")
        if current_entry in values:
            self._widgets["model_var"].set(current_entry)
        else:
            self._widgets["model_var"].set(select_initial_model(info, values))
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
        menu = thinking_menu_for(pid, model_id)
        previous = self._widgets["thinking_var"].get().strip().lower()
        allowed = {value for value, _ in menu}
        preferred = previous if previous in allowed else (
            os.getenv("MINI_AGENT_THINKING", "").strip().lower() or menu[0][0]
        )
        self._widgets["thinking_combo"].configure(
            values=[value for value, _ in menu],
            state="readonly",
        )
        self._widgets["thinking_var"].set(thinking_display_entry(menu, preferred))

    def _set_form_state(self, enabled: bool) -> None:
        """Enable or disable all interactive widgets during validation."""
        combo_state = "readonly" if enabled else "disabled"
        model_combo = self._widgets["model_combo"]
        thinking_combo = self._widgets["thinking_combo"]
        self._widgets["provider_combo"].configure(state=combo_state)
        model_combo.configure(state=combo_state if model_combo.cget("values") else "disabled")
        thinking_combo.configure(state=combo_state if thinking_combo.cget("values") else "disabled")
        self._widgets["api_entry"].configure(state="normal" if enabled else "disabled")
        self._widgets["verify_btn"].configure(state="normal" if enabled else "disabled")
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

    widgets = build_setup_widgets(dialog)
    controller = _SetupController(dialog, widgets)
    widgets["provider_combo"].focus_set()
    root.wait_window(dialog)
    return controller.result
