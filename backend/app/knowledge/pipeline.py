import asyncio
import json
import logging
import time
from pathlib import Path

from app.config import ROOT
from app.knowledge.chunk import chunk_units
from app.knowledge.clean import clean_units
from app.knowledge.dedupe import deduplicate
from app.knowledge.embed import embed_records
from app.knowledge.extract import ExtractionError, extract_source
from app.knowledge.normalize import redact_unit
from app.schemas.knowledge import IngestionReport, SourceEntry, SourceStatus

logger = logging.getLogger("darwix.ingest")


def load_manifest(settings):
    rows = json.loads(settings.manifest_path.read_text(encoding="utf-8-sig"))
    entries = [SourceEntry.model_validate(row) for row in rows]
    if len({entry.document_id for entry in entries}) != len(entries):
        raise ValueError("duplicate_document_id_in_manifest")
    for entry in entries:
        path = (ROOT / entry.path).resolve()
        if not path.is_relative_to(settings.raw_dir.resolve()):
            raise ValueError("source_outside_raw_directory")
    return entries


class IngestionPipeline:
    def __init__(self, settings, embedding, index):
        self.settings, self.embedding, self.index = settings, embedding, index
        self.lock = asyncio.Lock()

    async def run(self, paths=None, version=None, rebuild=False):
        async with self.lock:
            return await self._run(paths, version, rebuild)

    async def _run(self, paths, version, rebuild):
        started = time.perf_counter()
        entries = load_manifest(self.settings)
        if paths is not None:
            by_path = {entry.path: entry for entry in entries}
            if any(path not in by_path for path in paths):
                raise ValueError("paths_must_be_registered_in_manifest")
            entries = [by_path[path] for path in dict.fromkeys(paths)]
        if version:
            entries = [entry.model_copy(update={"version": version}) for entry in entries]
        report = IngestionReport(collection=self.index.alias, embedding_provider=self.embedding.signature)
        units = []
        terminology = self.settings.terminology()
        for entry in entries:
            try:
                extracted = await asyncio.to_thread(extract_source, entry, ROOT / entry.path)
                cleaned = clean_units(extracted, terminology)
                cleaned = [unit for unit in cleaned if unit.text.strip()]
                if not cleaned:
                    raise ExtractionError("empty_after_cleaning")
                units.extend(redact_unit(unit, self.settings.government_id_patterns) for unit in cleaned)
                report.sources.append(SourceStatus(document_id=entry.document_id, source=entry.path, status="success", unit_count=len(cleaned)))
            except ExtractionError as exc:
                logger.warning("source_extraction_failed", extra={"error_type": str(exc)})
                report.sources.append(SourceStatus(document_id=entry.document_id, source=entry.path, status="failed", error=str(exc)))
        units, report.dedupe_decisions = deduplicate(units, self.settings.near_duplicate_threshold)
        records = chunk_units(units, self.settings.chunk_words, self.settings.chunk_overlap_words)
        if rebuild and any(source.status == "failed" for source in report.sources):
            report.status, report.error = "failed", "rebuild_aborted_failed_sources_old_index_preserved"
        elif not records:
            report.status, report.error = "failed", "no_indexable_content_old_index_preserved"
        else:
            published = False
            try:
                if not rebuild:
                    replaced_ids = {source.document_id for source in report.sources if source.status == "success"}
                    retained = [record for record in await self.index.records() if record.document_id not in replaced_ids]
                    keys = {(r.product, r.language, r.version, r.category, r.checksum): r for r in retained}
                    unique = []
                    for record in records:
                        key = (record.product, record.language, record.version, record.category, record.checksum)
                        if key in keys:
                            report.dedupe_decisions.append({"document_id": record.document_id, "source": record.source,
                                "section": record.source_section, "decision": "exact_duplicate_of_retained_record_skipped",
                                "duplicate_of": keys[key].document_id, "canonical_record_id": keys[key].record_id})
                        else:
                            unique.append(record)
                    records = unique
                vectors = await embed_records(records, self.embedding, self.settings.provider_timeout_seconds)
                report.collection_records = await self.index.replace(records, vectors, rebuild=rebuild,
                    document_ids={source.document_id for source in report.sources if source.status == "success"})
                published = True
                report.indexed_records = len(records)
                report.status = "partial" if any(source.status == "failed" for source in report.sources) else "success"
                self.settings.normalized_dir.mkdir(parents=True, exist_ok=True)
                # Current complete redacted snapshot, including retained records.
                snapshot = await self.index.records()
                temporary = self.settings.normalized_dir / "records.jsonl.tmp"
                temporary.write_text("\n".join(record.model_dump_json() for record in snapshot) + "\n", encoding="utf-8")
                temporary.replace(self.settings.normalized_dir / "records.jsonl")
            except Exception as exc:
                logger.error("ingestion_provider_or_index_failed", extra={"error_type": type(exc).__name__})
                report.status, report.error = ("partial", "index_published_snapshot_export_failed") if published else ("failed", "provider_or_index_unavailable")
        report.duration_ms = round((time.perf_counter() - started) * 1000, 3)
        self.settings.normalized_dir.mkdir(parents=True, exist_ok=True)
        (self.settings.normalized_dir / "ingestion_report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
        logger.info("ingestion_complete", extra={"record_count": report.indexed_records, "duration_ms": report.duration_ms})
        return report
