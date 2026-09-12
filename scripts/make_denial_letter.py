"""Generates the synthetic Northstar Health denial letter fixture.

This is a deterministic PDF generator: calling ``render()`` twice must return
byte-identical output. That's achieved with reportlab's ``invariant=1``
(fixed document ID and dates instead of the current time) and
``pageCompression=0`` (uncompressed content streams, so the literal text used
by tests/fixtures/test_denial_letter.py appears directly in the raw PDF
bytes rather than inside a deflate stream). Only the plain Helvetica font is
used.

Values below are copied verbatim from docs/reclaim-speckit-prompts.md
Appendix A6 (the payer decision) and the task instructions: this is a
synthetic denial letter from "Northstar Health" for payer claim
PAYER-CLM-99281 (hospital claim HSP-CLM-100028), reason CO-50 (insufficient
documentation of medical necessity), decision date 2026-08-20, and an appeal
deadline of October 19, 2026 (2026-08-20 + 60-day appeal window).
"""

from __future__ import annotations

import io

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER

FONT_NAME = "Helvetica"
PAGE_WIDTH, PAGE_HEIGHT = LETTER

DOCUMENT_ID = "denial-letter-99281"
PAYER_CLAIM_ID = "PAYER-CLM-99281"
HOSPITAL_CLAIM_ID = "HSP-CLM-100028"
DENIAL_REASON_CODE = "CO-50"
DENIAL_REASON_TEXT = "Insufficient documentation of medical necessity"
DECISION_DATE_DISPLAY = "August 20, 2026"
APPEAL_DEADLINE_DISPLAY = "October 19, 2026"

LETTER_LINES = [
    "Northstar Health",
    "100 Synthetic Way",
    "Seattle, WA 98101",
    "",
    f"Date: {DECISION_DATE_DISPLAY}",
    f"Re: Claim {PAYER_CLAIM_ID} (Hospital claim {HOSPITAL_CLAIM_ID})",
    f"Document ID: {DOCUMENT_ID}",
    "",
    "NOTICE OF CLAIM DENIAL",
    "",
    "Dear Provider,",
    "",
    f"This letter confirms that claim {PAYER_CLAIM_ID}, submitted for",
    f"hospital claim {HOSPITAL_CLAIM_ID}, has been denied.",
    "",
    f"Reason code: {DENIAL_REASON_CODE}",
    f"Reason: {DENIAL_REASON_TEXT}",
    "",
    "Our review found that the documentation submitted with this claim",
    "did not sufficiently establish medical necessity for the billed",
    "service under the applicable coverage policy.",
    "",
    f"If you disagree with this decision, you may submit an appeal on",
    f"or before {APPEAL_DEADLINE_DISPLAY}. Appeals received after",
    f"{APPEAL_DEADLINE_DISPLAY} will not be considered.",
    "",
    "Appeals may be submitted through the provider portal or by fax.",
    "",
    "Sincerely,",
    "Northstar Health Claims Department",
    "",
    "SYNTHETIC DEMO DATA - this letter and every value in it are",
    "fictional and were generated for demonstration purposes only.",
]


def render() -> bytes:
    """Render the denial letter and return its raw PDF bytes.

    Deterministic: two calls (even in the same process, or in separate
    processes) produce byte-identical output, because ``invariant=1`` fixes
    reportlab's document ID and creation/modification dates instead of using
    wall-clock time or randomness.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(
        buffer,
        pagesize=LETTER,
        invariant=1,
        pageCompression=0,
    )
    c.setTitle(f"Northstar Health Denial Letter {DOCUMENT_ID}")
    c.setFont(FONT_NAME, 11)

    x_margin = 72
    y = PAGE_HEIGHT - 72
    line_height = 16

    for line in LETTER_LINES:
        if y < 72:
            c.showPage()
            c.setFont(FONT_NAME, 11)
            y = PAGE_HEIGHT - 72
        c.drawString(x_margin, y, line)
        y -= line_height

    c.showPage()
    c.save()
    return buffer.getvalue()


if __name__ == "__main__":
    from pathlib import Path

    output_path = Path(__file__).resolve().parents[1] / "fixtures" / "payer" / "denial-letter.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(render())
    print(f"Wrote {output_path} ({output_path.stat().st_size} bytes)")
