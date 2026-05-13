"""Tk font tuples for the GUI (platform-aware UI and monospace faces)."""

from __future__ import annotations

import os


def ui_font(size: int, *, bold: bool = False, italic: bool = False, overstrike: bool = False) -> tuple:
    """Return a Tk font tuple for the current platform.

    Args:
        size: Point size.
        bold: Whether to use a bold weight.
        italic: Whether to use an oblique/slant style.
        overstrike: Whether to draw a strikethrough line.

    Returns:
        Tk ``font`` tuple accepted by ``Text.tag_configure``.
    """
    family = "Segoe UI" if os.name == "nt" else "Helvetica"
    style: list[str] = []
    if bold:
        style.append("bold")
    if italic:
        style.append("italic")
    if overstrike:
        style.append("overstrike")
    if style:
        return (family, size, " ".join(style))
    return (family, size)


def mono_font(size: int, *, bold: bool = False) -> tuple:
    """Return a monospace font tuple.

    Args:
        size: Point size.
        bold: Whether to request bold weight.

    Returns:
        Tk font tuple.
    """
    family = "Consolas" if os.name == "nt" else "Menlo"
    if bold:
        return (family, size, "bold")
    return (family, size)
