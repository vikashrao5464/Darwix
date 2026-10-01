import csv
import json
import re
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup

from app.schemas.knowledge import ExtractedUnit, SourceEntry


class ExtractionError(ValueError):
    """Safe error code, without source contents or vendor exception messages."""


def split_headings(text: str):
    section, lines = None, []
    for line in text.splitlines():
        match = re.match(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            if any(line.strip() for line in lines):
                yield section, "\n".join(lines)
            section, lines = match[1], []
        else:
            lines.append(line)
    if any(line.strip() for line in lines):
        yield section, "\n".join(lines)


def extract_source(entry: SourceEntry, path: Path) -> list[ExtractedUnit]:
    def unit(text, page=None, section=None):
        return ExtractedUnit(document_id=entry.document_id, text=text, source=entry.path,
                             page=page, section=section, metadata=entry.model_dump())

    expected_suffixes = {"pdf": {".pdf"}, "html": {".html", ".htm"}, "markdown": {".md", ".markdown"},
                         "text": {".txt"}, "json": {".json"}, "csv": {".csv"}}
    if path.suffix.lower() not in expected_suffixes[entry.source_type]:
        raise ExtractionError("unsupported_file_type")
    try:
        units = []
        if entry.source_type == "pdf":
            with pymupdf.open(path) as document:
                for page_number, page in enumerate(document, start=1):
                    # Demo PDFs use explicit headings; PDFs without headings are
                    # conservatively chunked per page, without invented sections.
                    units.extend(unit(text, page_number, section) for section, text in split_headings(page.get_text()))
        elif entry.source_type == "html":
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
            for element in soup.select("nav, header, footer, aside, script, style, .navigation, .cookie-banner"):
                element.decompose()
            main = soup.find("main") or soup.find("article") or soup.body or soup
            for heading in main.find_all(re.compile(r"^h[1-6]$")):
                heading.replace_with("\n## " + heading.get_text(" ", strip=True) + "\n")
            units.extend(unit(text, section=section) for section, text in split_headings(main.get_text("\n")))
        elif entry.source_type in {"markdown", "text"}:
            units.extend(unit(text, section=section) for section, text in split_headings(path.read_text(encoding="utf-8-sig")))
        elif entry.source_type == "json":
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            rows = data if isinstance(data, list) else data.get("records", [data])
            if not isinstance(rows, list):
                raise ExtractionError("invalid_json_records")
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    raise ExtractionError("invalid_json_record")
                text = row.get("content", row.get("text"))
                if not isinstance(text, str):
                    text = "\n".join(f"{k}: {v}" for k, v in row.items())
                units.append(unit(text, section=str(row.get("title", f"Record {index + 1}"))))
        elif entry.source_type == "csv":
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    raise ExtractionError("empty_extraction")
                for index, row in enumerate(reader):
                    if None in row or any(value is None for value in row.values()):
                        raise ExtractionError("invalid_csv_row")
                    text = row.get("content") or "\n".join(f"{k}: {v}" for k, v in row.items())
                    units.append(unit(text, section=row.get("title") or f"Row {index + 2}"))
        units = [u for u in units if u.text.strip()]
        if not units:
            raise ExtractionError("empty_extraction")
        return units
    except ExtractionError:
        raise
    except FileNotFoundError:
        raise ExtractionError("source_not_found") from None
    except Exception:
        raise ExtractionError("corrupt_or_unreadable_source") from None
