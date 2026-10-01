import hashlib

from app.knowledge.normalize import normalized_hash
from app.schemas.knowledge import KnowledgeRecord


def chunk_units(units, chunk_words=400, overlap_words=60):
    records = []
    for unit in units:
        words = unit.text.split()
        if not words:
            continue
        start, chunk_number = 0, 0
        while start < len(words):
            end = min(start + chunk_words, len(words))
            # Prefer sentence ends over cutting a policy sentence in half.
            if end < len(words):
                for candidate in range(end, max(start + chunk_words // 2, end - 50), -1):
                    if words[candidate - 1].endswith((".", "!", "?")):
                        end = candidate
                        break
            content = " ".join(words[start:end])
            identity = f"{unit.document_id}|{unit.source}|{unit.page}|{unit.section}|{unit.metadata['version']}|{chunk_number}"
            record_id = "kb_" + unit.document_id + "_" + hashlib.sha256(identity.encode()).hexdigest()[:16]
            records.append(KnowledgeRecord(
                record_id=record_id, document_id=unit.document_id, title=unit.section or unit.document_id,
                content=content, category=unit.metadata["category"], product=unit.metadata["product"],
                source=unit.source, source_type=unit.metadata["source_type"], source_page=unit.page,
                source_section=unit.section, version=unit.metadata["version"],
                contains_pii=unit.metadata.get("contains_pii", False), language=unit.metadata["language"],
                checksum=normalized_hash(content), synthetic=unit.metadata.get("synthetic", True),
            ))
            if end == len(words):
                break
            start = max(start + 1, end - overlap_words)
            chunk_number += 1
    return records
