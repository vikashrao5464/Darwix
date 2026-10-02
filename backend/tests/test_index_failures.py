import json
from types import SimpleNamespace
from pathlib import Path

def test_remote_filter_index_migration_and_staging(indexed_client, monkeypatch):
    index = indexed_client.app.state.knowledge.index
    index.remote = True
    created = []
    async def info(collection): return SimpleNamespace(payload_schema={})
    async def create(**kwargs): created.append(kwargs)
    monkeypatch.setattr(index.client, 'get_collection', info)
    monkeypatch.setattr(index.client, 'create_payload_index', create)
    indexed_client.portal.call(index.ensure)
    assert {c['field_name'] for c in created} == {'product', 'language'}
    assert all(c['wait'] and c['field_schema'].value == 'keyword' for c in created)
    created.clear()
    assert indexed_client.post('/api/knowledge/ingest',json={'paths':['data/raw/demo_policy.pdf']}).json()['status']=='success'
    assert {c['field_name'] for c in created} == {'product', 'language'}

def test_filter_index_failure_preserves_active_alias(indexed_client, monkeypatch):
    index = indexed_client.app.state.knowledge.index
    original = indexed_client.portal.call(index._active_collection)
    async def failed(collection): raise ConnectionError('synthetic index failure')
    monkeypatch.setattr(index, 'ensure_filter_indexes', failed)
    assert indexed_client.post('/api/knowledge/ingest',json={'paths':['data/raw/demo_policy.pdf']}).json()['status']=='failed'
    assert indexed_client.portal.call(index._active_collection)==original
    assert indexed_client.post('/api/knowledge/answer',json={'query':'processing fee'}).json()['grounded']


def test_incremental_duplicates_not_indexed_twice(client):
    first = client.post("/api/knowledge/ingest", json={"paths":["data/raw/demo_eligibility.md"]}).json()
    second = client.post("/api/knowledge/ingest", json={"paths":["data/raw/demo_duplicate.md"]}).json()
    assert second["indexed_records"] == 1
    assert second["collection_records"] == first["collection_records"] + 1
    assert second["dedupe_decisions"][0]["decision"] == "exact_duplicate_of_retained_record_skipped"


def test_ingestion_embedding_failure_preserves_active_index(indexed_client, monkeypatch):
    service = indexed_client.app.state.knowledge
    async def invalid(texts):
        return []
    monkeypatch.setattr(service.embedding, "embed_documents", invalid)
    report = indexed_client.post("/api/knowledge/ingest", json={"paths":["data/raw/demo_policy.pdf"]}).json()
    assert report["status"] == "failed" and report["error"] == "provider_or_index_unavailable"
    answer = indexed_client.post("/api/knowledge/answer", json={"query":"processing fee"}).json()
    assert answer["grounded"] and "2 percent" in answer["answer"]


def test_staging_write_failure_preserves_alias(indexed_client, monkeypatch):
    service = indexed_client.app.state.knowledge
    original_collection = indexed_client.portal.call(service.index._active_collection)
    async def failed(*args, **kwargs):
        raise ConnectionError("synthetic staging failure")
    monkeypatch.setattr(service.index.client, "upsert", failed)
    report = indexed_client.post("/api/knowledge/ingest", json={"paths":["data/raw/demo_policy.pdf"]}).json()
    assert report["status"] == "failed"
    assert indexed_client.portal.call(service.index._active_collection) == original_collection
    assert indexed_client.post("/api/knowledge/answer", json={"query":"processing fee"}).json()["grounded"]


def test_failed_rebuild_preserves_previous_index(indexed_client, settings, tmp_path):
    missing = tmp_path / "missing.pdf"
    settings.raw_dir = tmp_path
    settings.manifest_path = tmp_path / "manifest.json"
    settings.manifest_path.write_text(json.dumps([{"document_id":"missing", "path":str(missing), "source_type":"pdf", "product":"business_loan", "version":"1.0"}]))
    report = indexed_client.portal.call(indexed_client.app.state.knowledge.pipeline.run, None, None, True)
    assert report.status == "failed" and "old_index_preserved" in report.error
    assert indexed_client.post("/api/knowledge/answer", json={"query":"processing fee"}).json()["grounded"]


def test_reingestion_replaces_old_document_version(indexed_client, settings):
    result = indexed_client.post("/api/knowledge/ingest", json={"paths":["data/raw/demo_policy.pdf"], "version":"2.0"}).json()
    assert result["status"] == "success"
    records = [json.loads(line) for line in (settings.normalized_dir / "records.jsonl").read_text().splitlines()]
    assert {r["version"] for r in records if r["document_id"] == "demo_policy"} == {"2.0"}
    assert {r["version"] for r in records if r["document_id"] == "demo_product"} == {"1.0"}
    answer = indexed_client.post("/api/knowledge/answer", json={"query":"processing fee"}).json()
    assert answer["citations"][0]["version"] == "2.0"


def test_mixed_unsupported_query_suppressed(indexed_client):
    result = indexed_client.post("/api/knowledge/answer", json={"query":"What is the processing fee for lunar tourism?"}).json()
    assert not result["grounded"] and not result["citations"]


def test_snapshot_export_failure_reports_published_index(indexed_client, monkeypatch):
    original_write = Path.write_text
    def fail_snapshot(path, *args, **kwargs):
        if path.name == "records.jsonl.tmp":
            raise OSError("synthetic export failure")
        return original_write(path, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", fail_snapshot)
    result = indexed_client.post("/api/knowledge/ingest", json={"paths":["data/raw/demo_policy.pdf"], "version":"2.0"}).json()
    assert result["status"] == "partial" and result["error"] == "index_published_snapshot_export_failed"
    assert result["indexed_records"] == 4
    answer = indexed_client.post("/api/knowledge/answer", json={"query":"processing fee"}).json()
    assert answer["grounded"] and answer["citations"][0]["version"] == "2.0"
