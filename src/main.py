from __future__ import annotations

from pip_system_certs.wrapt_requests import inject_truststore

inject_truststore()

from agent.runner import run_agent


def main() -> None:
    """Application entrypoint: start the mini-agent interactive session."""
    run_agent()


def main_gui() -> None:
    """Start the graphical mini-agent window (Tkinter)."""
    from agent.gui import run_gui

    run_gui()


if __name__ == "__main__":
    main()
