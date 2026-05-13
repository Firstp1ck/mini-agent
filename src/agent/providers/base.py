"""Common abstraction for the agent's LLM backends.

Each concrete subclass owns its own client, model, error mapping, and call
style. The rest of the agent (runner, prompt, tools) talks to these objects
through this small interface so that no provider-specific imports leak out.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Provider(ABC):
    """One configured LLM backend bundling client, model id, and call style.

    Attributes:
        name: Human-readable provider tag used in messages (for example
            ``"Anthropic"`` or ``"OpenAI"``).
        model: Resolved model id used for every ``call``.
    """

    name: str
    model: str

    @classmethod
    @abstractmethod
    def setup(cls) -> "Provider":
        """Build a ready-to-use provider.

        Implementations are expected to read environment variables, verify the
        API key, prompt the user when needed, persist new values to ``.env``,
        and finally return a fully initialized instance.

        Returns:
            A provider whose ``call`` method can be invoked immediately.
        """

    @abstractmethod
    def call(self, conversation: list[dict[str, str]]) -> str:
        """Send the conversation to the model and return assistant text.

        Args:
            conversation: First entry is the ``system`` message; remaining
                entries are ``user`` / ``assistant`` turns (including
                ``tool_result(...)`` user lines produced by the runner).

        Returns:
            Plain text content of the model's reply.

        Raises:
            SystemExit: When the underlying model id is not available to the
                account, with a message pointing at the provider's env var.
        """
