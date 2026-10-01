from app.schemas.retrieval import Citation


def citation(record):
    return Citation(record_id=record.record_id, source=record.source, source_type=record.source_type,
                    page=record.source_page, section=record.source_section, version=record.version,
                    synthetic=record.synthetic)
