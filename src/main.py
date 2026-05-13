from __future__ import annotations

from pip_system_certs.wrapt_requests import inject_truststore

inject_truststore()

from agent.runner import run_agent


def main() -> None:
    run_agent()


if __name__ == "__main__":
    main()
