"""Lightweight Markdown → Tkinter ``Text`` segments (chat-friendly subset).

Supports fenced code blocks, ATX headings, bullet lines, blockquotes, links,
bold, italic, inline code, and strikethrough. Unknown syntax falls through as
plain text.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from tkinter import Text as TkText

# Opening fence: ``` or ```lang then newline; closing: ``` on its own line or end.
_FENCE = re.compile(r"```([^\n\r]*)\r?\n(.*?)```", re.DOTALL)

_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_LINE = re.compile(r"^(\s*)[-*]\s+(.*)$")
_QUOTE_LINE = re.compile(r"^>\s?(.*)$")


def _parse_inline(rest: str, base: tuple[str, ...]) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Walk ``rest`` from the left, yielding styled segments.

    Args:
        rest: Remaining inline Markdown (may include newlines).
        base: Tk tag tuple applied to every emitted segment.

    Yields:
        ``(text, tags)`` tuples ready for ``Text.insert``.
    """
    while rest:
        if rest.startswith("~~"):
            end = rest.find("~~", 2)
            if end != -1:
                yield rest[2:end], base + ("md_strike",)
                rest = rest[end + 2 :]
                continue

        m_link = re.match(r"\[([^\]]*)\]\(([^)]*)\)", rest)
        m_code = re.match(r"`([^`]+)`", rest)
        m_bold_star = re.match(r"\*\*(.+?)\*\*", rest, re.DOTALL)
        m_bold_us = re.match(r"__(.+?)__", rest, re.DOTALL)
        m_italic_star = re.match(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", rest, re.DOTALL)
        m_italic_us = re.match(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", rest, re.DOTALL)

        candidates: list[tuple[int, re.Match[str], tuple[str, ...]]] = []
        if m_code:
            candidates.append((m_code.start(), m_code, base + ("md_code",)))
        if m_link:
            candidates.append((m_link.start(), m_link, base + ("md_link",)))
        if m_bold_star:
            candidates.append((m_bold_star.start(), m_bold_star, base + ("md_bold",)))
        if m_bold_us:
            candidates.append((m_bold_us.start(), m_bold_us, base + ("md_bold",)))
        if m_italic_star:
            candidates.append((m_italic_star.start(), m_italic_star, base + ("md_italic",)))
        if m_italic_us:
            candidates.append((m_italic_us.start(), m_italic_us, base + ("md_italic",)))

        earliest: tuple[int, re.Match[str], tuple[str, ...]] | None = None
        for item in candidates:
            if item[0] != 0:
                continue
            earliest = item
            break

        if earliest is None:
            # No recognized token at position 0: emit one character as plain.
            yield rest[0], base
            rest = rest[1:]
            continue

        _start, match, extra_tags = earliest
        if match is m_link:
            yield match.group(1), extra_tags
            url = match.group(2)
            if url:
                yield f" ({url})", base + ("md_link_url",)
            rest = rest[match.end() :]
            continue
        if match is m_code:
            yield match.group(1), extra_tags
            rest = rest[match.end() :]
            continue
        yield match.group(1), extra_tags
        rest = rest[match.end() :]


def _emit_line_as_markdown(
    line: str,
    base: tuple[str, ...],
    out: list[tuple[str, tuple[str, ...]]],
) -> None:
    """Parse one logical line (without trailing ``\\n``) into ``out``.

    Args:
        line: Single line of prose or list/quote content without newline.
        base: Base Tk tags for this line.
        out: Mutable list to extend with segments.
    """
    if not line.strip():
        out.append(("\n", base))
        return

    m_h = _ATX_HEADING.match(line)
    if m_h:
        level = min(len(m_h.group(1)), 3)
        tag = f"md_h{level}"
        out.extend(_parse_inline(m_h.group(2).strip(), base + (tag,)))
        out.append(("\n", base))
        return

    m_b = _BULLET_LINE.match(line)
    if m_b:
        out.append(("• ", base + ("md_list",)))
        out.extend(_parse_inline(m_b.group(2), base + ("md_list",)))
        out.append(("\n", base))
        return

    m_q = _QUOTE_LINE.match(line)
    if m_q:
        out.append(("│ ", base + ("md_quote",)))
        out.extend(_parse_inline(m_q.group(1), base + ("md_quote",)))
        out.append(("\n", base))
        return

    out.extend(_parse_inline(line, base))
    out.append(("\n", base))


def _iter_text_block_lines(block: str, base: tuple[str, ...]) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Turn a non-fence text block into tagged segments.

    Args:
        block: Markdown prose (no outer fence delimiters).
        base: Base Tk tags for this block.

    Yields:
        ``(text, tags)`` for ``Text.insert``.
    """
    if not block:
        return
    lines = block.split("\n")
    out: list[tuple[str, tuple[str, ...]]] = []
    for line in lines:
        _emit_line_as_markdown(line, base, out)
    yield from out


def iter_markdown_segments(markdown: str, base: tuple[str, ...]) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Split Markdown into Tk ``Text`` segments with tag tuples.

    Args:
        markdown: Full assistant (or user) message in Markdown.
        base: Bubble / role tags prepended to every segment.

    Yields:
        ``(fragment, tags)`` suitable for ``widget.insert("end", fragment, *tags)``.
    """
    pos = 0
    for match in _FENCE.finditer(markdown):
        if match.start() > pos:
            yield from _iter_text_block_lines(markdown[pos : match.start()], base)
        code_body = match.group(2)
        lang = (match.group(1) or "").strip()
        if lang:
            yield (f"{lang}\n", base + ("md_code_lang",))
        yield (code_body.rstrip("\n") + "\n", base + ("md_code_block",))
        pos = match.end()
    if pos < len(markdown):
        yield from _iter_text_block_lines(markdown[pos:], base)


def insert_markdown(widget: TkText, markdown: str, base_tags: tuple[str, ...]) -> None:
    """Append Markdown to a ``Text``/``ScrolledText`` widget at ``end``.

    Args:
        widget: Tk text widget (must not be ``disabled`` while inserting).
        markdown: Markdown source.
        base_tags: Tags applied to every fragment (for example bubble tags).
    """
    for fragment, tags in iter_markdown_segments(markdown, base_tags):
        if not fragment:
            continue
        if tags:
            widget.insert("end", fragment, *tags)
        else:
            widget.insert("end", fragment)
