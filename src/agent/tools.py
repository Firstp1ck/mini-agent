from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def resolve_abs_path(path_str: str) -> Path:
    """Resolve a user path relative to the current working directory."""
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def read_file(filename: str) -> dict[str, Any]:
    """
    Read and return the full text content of a file.
    :param filename: File path to read, absolute or relative to cwd.
    :return: Dict containing file_path and content, or an error.
    """
    path = resolve_abs_path(filename)
    try:
        return {"file_path": str(path), "content": path.read_text(encoding="utf-8")}
    except Exception as exc:
        return {"file_path": str(path), "error": f"{type(exc).__name__}: {exc}"}


def list_files(path: str = ".") -> dict[str, Any]:
    """
    List direct children of a directory.
    :param path: Directory path to list, absolute or relative to cwd.
    :return: Dict containing path and files with filename/type, or an error.
    """
    full_path = resolve_abs_path(path)
    try:
        files = [
            {"filename": item.name, "type": "file" if item.is_file() else "dir"}
            for item in sorted(full_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        ]
        return {"path": str(full_path), "files": files}
    except Exception as exc:
        return {"path": str(full_path), "error": f"{type(exc).__name__}: {exc}"}


def edit_file(path: str, old_str: str, new_str: str) -> dict[str, Any]:
    """
    Replace the first occurrence of old_str with new_str in a file.
    If old_str is empty, create or overwrite the file with new_str.
    :param path: File path to edit, absolute or relative to cwd.
    :param old_str: Existing text to replace. Empty string means create/overwrite.
    :param new_str: Replacement text or full file content when creating.
    :return: Dict containing path and action, or an error.
    """
    full_path = resolve_abs_path(path)
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if old_str == "":
            full_path.write_text(new_str, encoding="utf-8")
            return {"path": str(full_path), "action": "created_or_overwritten"}

        original = full_path.read_text(encoding="utf-8")
        if old_str not in original:
            return {"path": str(full_path), "action": "old_str_not_found"}

        full_path.write_text(original.replace(old_str, new_str, 1), encoding="utf-8")
        return {"path": str(full_path), "action": "edited"}
    except Exception as exc:
        return {"path": str(full_path), "error": f"{type(exc).__name__}: {exc}"}


def bash(command: str, timeout: int = 30) -> dict[str, Any]:
    """
    Execute a bash command in the current working directory and return its output.
    Use this for safe inspection commands, tests, linters, and small scripts.
    Avoid destructive commands unless the user explicitly requested them.
    :param command: Bash command to execute.
    :param timeout: Maximum runtime in seconds, capped at 120.
    :return: Dict containing command, exit_code, stdout, stderr, and timed_out.
    """
    bounded_timeout = max(1, min(int(timeout), 120))
    try:
        completed = subprocess.run(
            ["bash", "-lc", command],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            timeout=bounded_timeout,
            check=False,
        )
        return {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-12000:],
            "stderr": completed.stderr[-12000:],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "exit_code": None,
            "stdout": (exc.stdout or "")[-12000:],
            "stderr": (exc.stderr or "")[-12000:],
            "timed_out": True,
            "timeout": bounded_timeout,
        }
    except Exception as exc:
        return {"command": command, "error": f"{type(exc).__name__}: {exc}"}


TOOL_REGISTRY = {
    "read_file": read_file,
    "list_files": list_files,
    "edit_file": edit_file,
    "bash": bash,
}
