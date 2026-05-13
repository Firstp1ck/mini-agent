from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any


def resolve_abs_path(path_str: str) -> Path:
    """Resolve a path string to an absolute ``Path`` (cwd for relative paths).

    Args:
        path_str: User-supplied path; ``~`` is expanded.

    Returns:
        Absolute, resolved path.
    """
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def read_file(filename: str) -> dict[str, Any]:
    """Read the full text of a file as UTF-8.

    Args:
        filename: Path to read, absolute or relative to the current working directory.

    Returns:
        Dict with ``file_path`` and ``content``, or ``file_path`` and ``error``.
    """
    path = resolve_abs_path(filename)
    try:
        return {"file_path": str(path), "content": path.read_text(encoding="utf-8")}
    except Exception as exc:
        return {"file_path": str(path), "error": f"{type(exc).__name__}: {exc}"}


def list_files(path: str = ".") -> dict[str, Any]:
    """List immediate children of a directory with basic file/dir typing.

    Args:
        path: Directory to list, absolute or relative to cwd. Defaults to ``.``.

    Returns:
        Dict with ``path`` and ``files`` (each entry has ``filename`` and ``type``),
        or ``path`` and ``error``.
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
    """Replace the first occurrence of ``old_str`` with ``new_str``, or create the file.

    If ``old_str`` is empty, writes ``new_str`` as the full file contents (create or
    overwrite). Otherwise performs a single in-place replace after reading UTF-8 text.

    Args:
        path: File path, absolute or relative to cwd.
        old_str: Substring to replace once; empty means create/overwrite.
        new_str: Replacement substring or entire file body when creating.

    Returns:
        Dict with ``path`` and ``action`` (``edited``, ``created_or_overwritten``,
        or ``old_str_not_found``), or ``path`` and ``error``.
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
    """Run a bash one-liner in the current working directory and capture output.

    Intended for inspection, tests, linters, and small scripts. Prefer non-destructive
    commands unless the user explicitly asked for mutating operations.

    Args:
        command: Shell command passed to ``bash -lc``.
        timeout: Max runtime in seconds, clamped to the range ``[1, 120]``.

    Returns:
        Dict with ``command``, ``exit_code``, ``stdout``, ``stderr``, and
        ``timed_out``; on timeout, may include ``timeout``; on other failures,
        ``command`` and ``error``.
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


def _work_dirs_read_file(args: dict[str, object]) -> list[Path]:
    """Return directories to scan for guides after a ``read_file`` call.

    Args:
        args: Tool kwargs; uses string ``filename`` when present.

    Returns:
        One directory (the file's parent, or the path itself if it is a directory),
        or an empty list when ``filename`` is missing or not a string.
    """
    raw = args.get("filename")
    if not isinstance(raw, str):
        return []
    path = resolve_abs_path(raw)
    if path.is_dir():
        return [path]
    return [path.parent]


def _work_dirs_list_files(args: dict[str, object]) -> list[Path]:
    """Return directories to scan for guides after a ``list_files`` call.

    Args:
        args: Tool kwargs; uses string ``path`` (default ``.``) when valid.

    Returns:
        One directory matching the listed path, or an empty list when ``path`` is
        not a string.
    """
    raw = args.get("path", ".")
    if not isinstance(raw, str):
        return []
    return [resolve_abs_path(raw)]


def _work_dirs_edit_file(args: dict[str, object]) -> list[Path]:
    """Return directories to scan for guides after an ``edit_file`` call.

    Args:
        args: Tool kwargs; uses string ``path`` when present.

    Returns:
        The target file's parent directory, or an empty list when ``path`` is
        missing or not a string.
    """
    raw = args.get("path")
    if not isinstance(raw, str):
        return []
    return [resolve_abs_path(raw).parent]


def _work_dirs_bash(_args: dict[str, object]) -> list[Path]:
    """Return directories to scan for guides after a ``bash`` call.

    Args:
        _args: Ignored; ``bash`` always runs in the process current working directory.

    Returns:
        A single-element list containing ``Path.cwd()``.
    """
    return [Path.cwd()]


_TOOL_WORK_DIRECTORY_RESOLVERS: dict[str, Callable[[dict[str, object]], list[Path]]] = {
    "read_file": _work_dirs_read_file,
    "list_files": _work_dirs_list_files,
    "edit_file": _work_dirs_edit_file,
    "bash": _work_dirs_bash,
}


def work_directories_for_tool(tool_name: str, args: dict[str, object]) -> list[Path]:
    """Resolve directories touched by a tool call for ``AGENTS.md`` / ``CLAUDE.md`` walks.

    Only tools registered in ``_TOOL_WORK_DIRECTORY_RESOLVERS`` contribute paths;
    unknown tools return an empty list.

    Args:
        tool_name: Key present in ``TOOL_REGISTRY``.
        args: Keyword arguments passed to the tool implementation.

    Returns:
        Zero or more absolute directory paths to search for project guide files.
    """
    resolver = _TOOL_WORK_DIRECTORY_RESOLVERS.get(tool_name)
    if resolver is None:
        return []
    return resolver(args)


TOOL_REGISTRY = {
    "read_file": read_file,
    "list_files": list_files,
    "edit_file": edit_file,
    "bash": bash,
}
