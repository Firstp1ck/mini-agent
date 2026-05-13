# Agent guide: mini-agent

This document helps automated agents and contributors find their way around the repository and follow project conventions when changing code.

## What this project is

**mini-agent** is a small Python CLI that runs an interactive loop with an Anthropic model. The model can call local tools (`read_file`, `list_files`, `edit_file`, `bash`). Entrypoint: `src/main.py` → `agent.runner.run_agent`. Package layout is under `src/` (Hatch `sources = ["src"]`).

## Repository map

| Path | Role |
|------|------|
| `src/main.py` | CLI entry: trust-store injection, then `run_agent()`. |
| `src/agent/runner.py` | REPL loop, conversation state, tool dispatch. |
| `src/agent/tools.py` | Tool definitions, registry, implementations. |
| `src/agent/llm.py` | Model API calls and parsing of tool invocations from text. |
| `src/agent/prompt.py` | System prompt text for the agent. |
| `src/agent/config.py` | Env loading, API client/model resolution, defaults. |
| `pyproject.toml` | Dependencies, scripts (`mini-agent = "main:main"`), build config. |
| `packaging/pyinstaller/*.spec` | PyInstaller specs (local Windows build; CI release matrix). |
| `packaging/windows/mini-agent.nsi` | NSIS installer script used by the release workflow (Windows). |
| `README.md` | User-facing install and run instructions. |

When adding behavior, prefer the smallest change that fits the existing module boundaries. If a file grows toward the line limit (see rules below), split by responsibility (e.g. new submodule under `src/agent/`) rather than inflating one file.

## How to run and verify

- Sync and run: `uv sync` then `uv run mini-agent` (see `README.md`).
- Python version: **3.11+** (`requires-python` in `pyproject.toml`).

## Coding rules

Follow these rules for all new and modified code in this repository.

### Modularity

- Keep the codebase **modular**: separate concerns into focused modules and small, composable units.
- Prefer **one clear responsibility per file**; avoid “god” modules that mix unrelated logic.

### Size limits

- **Functions:** no function body may exceed **100 lines** (count from the `def` line through the end of the function, inclusive of the docstring). If you approach that limit, extract helpers or move logic to a dedicated function or module.
- **Files:** no source file may exceed **600 lines**. If a file approaches that limit, split it along natural boundaries and update imports.

### Documentation

- **Every function** (including `async` functions, methods, and nested functions intended for reuse) must have a **docstring** immediately under the signature.
- Use Google- or NumPy-style consistently with the surrounding file. Include purpose, important parameters and return values where non-obvious, and `Raises:` when the function intentionally raises.

### Idiomatic Python

- Write **idiomatic** Python 3.11+: type hints where they aid clarity, `pathlib` for paths, context managers for resources, explicit errors over silent failures, and patterns that match the existing codebase.
- Use `from __future__ import annotations` in new modules if the project already does so in neighboring files.
- Match import order and naming style used in `src/agent/`.

### General expectations

- Do not weaken security or safety notes already documented for tools (e.g. unsandboxed `bash`).
- Keep changes minimal and reviewable; avoid unrelated refactors in the same change as a feature fix.
