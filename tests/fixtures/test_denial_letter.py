"""Validation tests for the synthetic Northstar Health denial letter PDF.

Imports scripts/make_denial_letter.py (repo root is a package via
scripts/__init__.py) and checks: render() is deterministic, the on-disk
fixture matches render() exactly, and the required literal substrings are
present in the raw PDF bytes (reportlab is configured with
pageCompression=0 specifically so these appear uncompressed).
"""

from __future__ import annotations

from pathlib import Path

from scripts.make_denial_letter import render

REPO_ROOT = Path(__file__).resolve().parents[2]
DENIAL_LETTER_PDF_PATH = REPO_ROOT / "fixtures" / "payer" / "denial-letter.pdf"

REQUIRED_SUBSTRINGS = [
    b"October 19, 2026",
    b"denial-letter-99281",
    b"PAYER-CLM-99281",
    b"CO-50",
    b"SYNTHETIC DEMO DATA",
]


def test_render_is_deterministic():
    first = render()
    second = render()
    assert first == second


def test_render_matches_fixture_pdf_on_disk():
    assert DENIAL_LETTER_PDF_PATH.is_file(), (
        "fixtures/payer/denial-letter.pdf is missing; run "
        "`uv run python scripts/make_denial_letter.py` to generate it"
    )
    on_disk = DENIAL_LETTER_PDF_PATH.read_bytes()
    rendered = render()
    assert on_disk == rendered


def test_pdf_bytes_contain_required_substrings():
    pdf_bytes = render()
    assert pdf_bytes.startswith(b"%PDF-")
    for substring in REQUIRED_SUBSTRINGS:
        assert substring in pdf_bytes, substring


def test_fixture_on_disk_contains_required_substrings():
    on_disk = DENIAL_LETTER_PDF_PATH.read_bytes()
    for substring in REQUIRED_SUBSTRINGS:
        assert substring in on_disk, substring
