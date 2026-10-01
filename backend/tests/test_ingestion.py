import json
from pathlib import Path

import pymupdf
import pytest

from app.config import ROOT
from app.knowledge.chunk import chunk_units
from app.knowledge.clean import clean_text, clean_units
from app.knowledge.dedupe import deduplicate
from app.knowledge.extract import ExtractionError, extract_source
from app.knowledge.normalize import redact_unit
from app.knowledge.pii import redact_pii
from app.schemas.knowledge import ExtractedUnit, SourceEntry


def source(kind, path):
    return SourceEntry(document_id="test", path=str(path), source_type=kind, product="business_loan", version="1.0", category="qualification")


def unit(text, document_id="fixture", section="Eligibility", page=None):
    return ExtractedUnit(document_id=document_id, text=text, source="fixture.pdf", page=page, section=section,
        metadata={"category":"qualification", "product":"business_loan", "source_type":"pdf", "version":"1.0", "language":"en", "synthetic":True})


def test_pdf_source_pages_and_boilerplate(settings):
    path = ROOT / "data/raw/demo_policy.pdf"
    units = extract_source(source("pdf", path), path)
    assert {u.page for u in units} == {1, 2}
    cleaned = clean_units(units, settings.terminology())
    assert any(u.section == "Processing fees" and u.page == 1 for u in cleaned)
    assert any(u.section == "Early repayment" and u.page == 2 for u in cleaned)
    assert "Synthetic Demo Policy - Header" not in " ".join(u.text for u in cleaned)
    assert "Synthetic Demo Policy - Footer" not in " ".join(u.text for u in cleaned)
    assert "2 percent" in " ".join(u.text for u in cleaned)


@pytest.mark.parametrize("kind,name,section", [
    ("html", "demo_faq.html", "Required documents"),
    ("markdown", "demo_eligibility.md", "Minimum business age"),
    ("text", "demo_rates.txt", "Interest rates"),
    ("json", "demo_product.json", "Loan amount limits"),
    ("csv", "demo_support.csv", "Human escalation"),
])
def test_extract_formats(kind, name, section):
    path = ROOT / "data/raw" / name
    units = extract_source(source(kind, path), path)
    assert any(u.section == section and u.text.strip() for u in units)
    assert all(u.source == str(path) for u in units)
    if kind == "html":
        text = " ".join(u.text for u in units)
        assert "Home | Login" not in text
        assert "unwanted navigation" not in text


@pytest.mark.parametrize("suffix,kind,content,error", [
    (".pdf", "pdf", b"broken PDF", "corrupt_or_unreadable_source"),
    (".json", "json", b"{broken", "corrupt_or_unreadable_source"),
    (".txt", "text", b"   ", "empty_extraction"),
    (".zip", "text", b"data", "unsupported_file_type"),
    (".csv", "csv", b"a,b\n1\n", "invalid_csv_row"),
])
def test_extraction_failures(tmp_path, suffix, kind, content, error):
    path = tmp_path / ("invalid" + suffix)
    path.write_bytes(content)
    with pytest.raises(ExtractionError, match=error):
        extract_source(source(kind, path), path)


def test_empty_pdf_and_missing_source(tmp_path):
    path = tmp_path / "empty.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.save(path)
    with pytest.raises(ExtractionError, match="empty_extraction"):
        extract_source(source("pdf", path), path)
    missing = tmp_path / "missing.txt"
    with pytest.raises(ExtractionError, match="source_not_found"):
        extract_source(source("text", missing), missing)


def test_cleaning_fixture(settings):
    fixture = json.loads((ROOT / "data/fixtures/cleaning.json").read_text(encoding="utf-8"))
    assert clean_text(fixture["before"], settings.terminology()) == fixture["after"]


@pytest.mark.parametrize("text,marker", [
    ("Email person@example.invalid", "[EMAIL_REDACTED]"),
    ("Call +91 98765 43210", "[PHONE_REDACTED]"),
    ("Phone 9876543210", "[PHONE_REDACTED]"),
    ("Phone (202) 555-0142", "[PHONE_REDACTED]"),
    ("Card 4111 1111 1111 1111", "[ACCOUNT_REDACTED]"),
    ("Account 123456789012345678901234", "[ACCOUNT_REDACTED]"),
    ("ID 123-45-6789", "[GOV_ID_REDACTED]"),
    ("ID 1234 5678 9012", "[GOV_ID_REDACTED]"),
])
def test_pii_positive(text, marker):
    result = redact_pii(text)
    assert result.contains_pii
    assert marker in result.redacted_text


@pytest.mark.parametrize("text", ["24 months", "2 percent", "INR 1200000", "INR 1000000000", "Turnover: 12345678901234", "2026-10-01", "INR 1,200,000"])
def test_business_numbers_preserved(text):
    assert redact_pii(text).redacted_text == text
    assert not redact_pii(text).contains_pii


def test_configured_government_id_and_metadata():
    assert redact_pii("ID GOV-123456", [r"\bGOV-\d{6}\b"]).redacted_text == "ID [GOV_ID_REDACTED]"
    protected = redact_unit(unit("Email demo@example.invalid", section="Call 9876543210"), [])
    assert protected.metadata["contains_pii"]
    assert "demo@" not in protected.text
    assert "9876543210" not in protected.section


def test_exact_dedupe_and_near_duplicate_kept():
    content = "The minimum annual turnover is INR 1200000. Turnover must be confirmed by the applicant and verified against documents before a final lending decision."
    units, decisions = deduplicate([unit(content), unit(content.upper(), "copy"), unit(content + " Confirm this.", "near")], 0.85)
    assert len(units) == 2
    assert {d["decision"] for d in decisions} == {"exact_duplicate_skipped", "near_duplicate_flagged_kept"}


def test_dedupe_does_not_merge_products_versions_or_numeric_conflicts():
    original = unit("Applicants must have operated a business for at least 24 months with verified annual turnover.")
    conflict = unit(original.text.replace("24", "12"), "conflict")
    another_product = unit(original.text, "another")
    another_product.metadata["product"] = "insurance"
    another_version = unit(original.text, "version")
    another_version.metadata["version"] = "2.0"
    units, _ = deduplicate([original, conflict, another_product, another_version], 0.8)
    assert len(units) == 4


def test_chunks_preserve_traceability_and_boundaries():
    units = [unit(" ".join(f"word{i}" for i in range(125)), page=4), unit("Unrelated section must remain separate.", section="Fees", page=5)]
    records = chunk_units(units, chunk_words=50, overlap_words=10)
    assert len(records) == 4
    assert all(len(r.content.split()) <= 50 for r in records)
    assert records[0].content.split()[-10:] == records[1].content.split()[:10]
    assert all(r.source_page == 4 for r in records[:-1])
    assert records[-1].source_section == "Fees" and records[-1].source_page == 5
    assert all(r.checksum.startswith("sha256:") and r.record_id for r in records)
    assert [r.record_id for r in records] == [r.record_id for r in chunk_units(units, 50, 10)]
