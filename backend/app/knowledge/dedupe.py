import re

from app.knowledge.normalize import normalized_hash


def deduplicate(units, threshold=0.88):
    kept, decisions, exact = [], [], {}
    for unit in units:
        scope = tuple(unit.metadata.get(k) for k in ("product", "language", "version", "category"))
        key = (scope, normalized_hash(unit.text))
        identity = {"document_id": unit.document_id, "source": unit.source, "page": unit.page, "section": unit.section}
        if key in exact:
            original = exact[key]
            # Preserve a PII flag even if a duplicate adds another redacted example.
            original.metadata["contains_pii"] = original.metadata.get("contains_pii", False) or unit.metadata.get("contains_pii", False)
            decisions.append({**identity, "decision": "exact_duplicate_skipped", "duplicate_of": original.document_id,
                              "canonical_section": original.section})
            continue
        tokens = set(re.findall(r"\w+", unit.text.casefold()))
        for original in kept:
            if tuple(original.metadata.get(k) for k in ("product", "language", "version", "category")) != scope:
                continue
            original_tokens = set(re.findall(r"\w+", original.text.casefold()))
            similarity = len(tokens & original_tokens) / max(1, len(tokens | original_tokens))
            if similarity >= threshold:
                decisions.append({**identity, "decision": "near_duplicate_flagged_kept", "similar_to": original.document_id,
                                  "similarity": round(similarity, 4)})
                break
        exact[key] = unit
        kept.append(unit)
    return kept, decisions
