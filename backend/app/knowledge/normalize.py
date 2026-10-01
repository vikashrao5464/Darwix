import hashlib

from app.knowledge.pii import redact_pii


def normalized_hash(text):
    normalized = " ".join(text.casefold().split())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def redact_unit(unit, government_patterns):
    text = redact_pii(unit.text, government_patterns)
    section = redact_pii(unit.section or "", government_patterns)
    return unit.model_copy(update={
        "text": text.redacted_text,
        "section": section.redacted_text or None,
        "metadata": {**unit.metadata, "contains_pii": text.contains_pii or section.contains_pii},
    })
