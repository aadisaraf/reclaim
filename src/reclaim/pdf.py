"""Renders an appeal Letter as a deterministic PDF and as HTML.

Determinism matches scripts/make_denial_letter.py: reportlab's ``invariant=1`` fixes the
document ID and creation/modification dates instead of using wall-clock time, and
``pageCompression=0`` leaves the content stream uncompressed so plain-ASCII text (like
"SYNTHETIC DEMO DATA") appears directly in the raw PDF bytes. Only the built-in Helvetica font
is used, so no font subsetting can introduce nondeterminism either.
"""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from reclaim.models import Letter

FONT_NAME = "Helvetica"
PAGE_WIDTH, PAGE_HEIGHT = LETTER
X_MARGIN = 72
TOP_Y = PAGE_HEIGHT - 72
BOTTOM_Y = 84
LINE_HEIGHT = 14


def _wrap(text: str, width: int = 95) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _letter_lines(letter: Letter) -> list[str]:
    lines = [f"APPEAL FOR RECONSIDERATION -- Packet version: v{letter.version}", ""]

    lines.append("Claim details:")
    for field in letter.header:
        lines.append(f"  {field.label}: {field.value}")
    lines.append("")

    lines.append("Statement of medical necessity:")
    for i, statement in enumerate(letter.body, start=1):
        citations = ", ".join(statement.citation_ids)
        for wrapped in _wrap(f"{i}. {statement.text} [{citations}]"):
            lines.append(f"  {wrapped}")
    lines.append("")

    lines.append(f"Requested action: {letter.requested_action}")
    lines.append("")

    lines.append("Attachments:")
    for attachment in letter.attachments:
        lines.append(f"  - {attachment}")
    lines.append("")

    lines.append(f"Required approver: {letter.required_approver}")
    return lines


def render_pdf(letter: Letter) -> bytes:
    """Render the appeal packet letter to raw PDF bytes.

    Deterministic: two calls with an equal ``letter`` produce byte-identical output (see the
    module docstring). The footer (``letter.footer``, "SYNTHETIC DEMO DATA" by default) is
    drawn on every page.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER, invariant=1, pageCompression=0)
    c.setTitle(f"Appeal Packet v{letter.version}")

    def draw_footer() -> None:
        c.setFont(FONT_NAME, 8)
        c.drawString(X_MARGIN, 48, letter.footer)

    c.setFont(FONT_NAME, 10)
    y = TOP_Y
    for line in _letter_lines(letter):
        if y < BOTTOM_Y:
            draw_footer()
            c.showPage()
            c.setFont(FONT_NAME, 10)
            y = TOP_Y
        c.drawString(X_MARGIN, y, line)
        y -= LINE_HEIGHT

    draw_footer()
    c.showPage()
    c.save()
    return buffer.getvalue()


def _esc(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def render_html(letter: Letter) -> str:
    """Render the appeal packet letter as a self-contained HTML fragment.

    Each body statement carries its requirement and citation ids as data attributes so the
    Packet tab (web/app/cases/[caseId]/PacketTab.tsx, out of scope here) can highlight the
    matching requirement and excerpt on click.
    """
    header_rows = "".join(
        f"<tr><th>{_esc(field.label)}</th><td>{_esc(field.value)}</td>"
        f"<td class=\"source\">{_esc(field.source)}</td></tr>"
        for field in letter.header
    )
    body_items = "".join(
        f"<li data-statement-id=\"{_esc(statement.statement_id)}\" "
        f"data-requirement-ids=\"{_esc(','.join(statement.requirement_ids))}\" "
        f"data-citation-ids=\"{_esc(','.join(statement.citation_ids))}\">{_esc(statement.text)}</li>"
        for statement in letter.body
    )
    attachment_items = "".join(f"<li>{_esc(a)}</li>" for a in letter.attachments)

    return (
        "<article class=\"appeal-packet\">"
        f"<h1>Appeal for Reconsideration (v{letter.version})</h1>"
        f"<table class=\"header\">{header_rows}</table>"
        f"<section class=\"body\"><ol>{body_items}</ol></section>"
        f"<p class=\"requested-action\">{_esc(letter.requested_action)}</p>"
        f"<ul class=\"attachments\">{attachment_items}</ul>"
        f"<p class=\"required-approver\">Requires approval by: {_esc(letter.required_approver)}</p>"
        f"<footer>{_esc(letter.footer)}</footer>"
        "</article>"
    )
