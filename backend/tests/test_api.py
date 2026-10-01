import asyncio
import json
import logging
from io import StringIO

from app.knowledge.pipeline import load_manifest
from app.knowledge.retrieve import FALLBACK
from app.logging_config import JsonFormatter
from app.providers.llm import EvidenceQuote, EvidenceSelection


def test_health_cors_and_validation(client):
    response = client.get("/health", headers={"Origin":"http://localhost:5173"})
    assert response.json() == {"status":"ok"}
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["x-request-id"]
    response = client.get("/health", headers={"Origin":"https://untrusted.invalid"})
    assert "access-control-allow-origin" not in response.headers
    assert client.post("/api/knowledge/search", json={"query":"   "}).status_code == 422
    invalid = client.post("/api/knowledge/search", json={"query":"secret@example.invalid", "top_k":999})
    assert invalid.status_code == 422
    assert "secret@" not in invalid.text


def test_sqlite_initialized_and_clean_index_fallback(client):
    answer = client.post("/api/knowledge/answer", json={"query":"What documents are required?"}).json()
    assert not answer["grounded"] and not answer["citations"]
    assert answer["answer"] == FALLBACK


def test_ingest_report_and_idempotency(indexed_client, settings):
    body = {"paths":[entry.path for entry in load_manifest(settings)], "version":"1.0"}
    first = indexed_client.post("/api/knowledge/ingest", json=body).json()
    second = indexed_client.post("/api/knowledge/ingest", json=body).json()
    assert first["indexed_records"] == second["collection_records"]
    assert any(d["decision"] == "exact_duplicate_skipped" for d in first["dedupe_decisions"])
    assert any(d["decision"] == "near_duplicate_flagged_kept" for d in first["dedupe_decisions"])
    records = [json.loads(line) for line in (settings.normalized_dir / "records.jsonl").read_text().splitlines()]
    assert len(records) >= 10
    assert all(record["synthetic"] and record["source"] and record["version"] for record in records)
    assert all("support@example" not in record["content"] and "98765" not in record["content"] for record in records)
    assert any(record["contains_pii"] and "[EMAIL_REDACTED]" in record["content"] for record in records)


def test_known_answer_citations(indexed_client):
    response = indexed_client.post("/api/knowledge/answer", json={"query":"What is the processing fee?"})
    answer = response.json()
    assert answer["grounded"], answer
    assert "2 percent" in answer["answer"]
    assert answer["answer"].startswith("Synthetic demo information")
    citation = answer["citations"][0]
    assert citation["source"] == "data/raw/demo_policy.pdf" and citation["page"] == 1
    assert citation["record_id"] and citation["version"] == "1.0"


def test_unknown_and_filtered_queries_fallback(indexed_client):
    bodies = [{"query":"What is the cashback promotion for lunar tourism?"},
              {"query":"What is the processing fee?", "product":"life_insurance"},
              {"query":"What is the processing fee?", "language":"fil"}]
    for body in bodies:
        result = indexed_client.post("/api/knowledge/answer", json=body).json()
        assert result["answer"] == FALLBACK and not result["grounded"] and result["citations"] == []


def test_top_k_scores_metadata_and_redacted_query(indexed_client):
    result = indexed_client.post("/api/knowledge/search", json={"query":"What is the processing fee? Email me at customer@example.invalid", "top_k":2}).json()
    assert len(result["records"]) == 2
    assert "customer@example" not in result["query"]
    assert result["records"][0]["score"] >= result["records"][1]["score"]
    assert all(record["product"] == "business_loan" and record["language"] == "en" and record["checksum"] for record in result["records"])


def test_unregistered_and_traversal_paths_rejected(client):
    for path in ("../../.env", "C:/Windows/win.ini", "data/raw/not_registered.txt"):
        assert client.post("/api/knowledge/ingest", json={"paths":[path]}).status_code == 400


def test_failed_source_report_and_successful_sources_continue(client, settings, tmp_path):
    good = tmp_path / "good.txt"
    good.write_text("## Test eligibility\nMinimum business age is 24 months.")
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a PDF")
    settings.raw_dir = tmp_path
    settings.manifest_path = tmp_path / "manifest.json"
    entries = [{"document_id":name, "path":str(path), "source_type":kind, "product":"business_loan", "version":"1.0"}
               for name, path, kind in [("good", good, "text"), ("bad", bad, "pdf")]]
    settings.manifest_path.write_text(json.dumps(entries))
    result = client.post("/api/knowledge/ingest", json={"paths":[str(good),str(bad)]}).json()
    assert result["status"] == "partial" and result["indexed_records"] == 1
    assert result["sources"][1]["status"] == "failed"
    assert result["sources"][1]["error"] == "corrupt_or_unreadable_source"


def test_embedding_timeout_is_safe_and_cancels(indexed_client, settings, monkeypatch):
    service = indexed_client.app.state.knowledge
    settings.provider_timeout_seconds = 0.01
    cancelled = []
    async def slow(text):
        try:
            await asyncio.sleep(1)
        finally:
            cancelled.append(True)
    monkeypatch.setattr(service.embedding, "embed_query", slow)
    result = indexed_client.post("/api/knowledge/answer", json={"query":"processing fee"}).json()
    assert result["answer"] == FALLBACK and not result["grounded"]
    assert result["reason"] == "provider_or_index_unavailable"
    assert cancelled


def test_llm_timeout_and_invalid_evidence(indexed_client, settings, monkeypatch):
    service = indexed_client.app.state.knowledge
    async def slow(query, records):
        await asyncio.sleep(1)
    monkeypatch.setattr(service.llm, "select_evidence", slow)
    settings.provider_timeout_seconds = 0.05
    result = indexed_client.post("/api/knowledge/answer", json={"query":"processing fee"}).json()
    assert not result["grounded"] and result["reason"] == "answer_provider_unavailable"
    async def invented(query, records):
        return EvidenceSelection(quotes=[EvidenceQuote(record_id=records[0].record_id, text="The loan is guaranteed approved.")])
    monkeypatch.setattr(service.llm, "select_evidence", invented)
    result = indexed_client.post("/api/knowledge/answer", json={"query":"processing fee"}).json()
    assert not result["grounded"] and result["reason"] == "invalid_provider_evidence"
    async def wrong_id(query, records):
        return EvidenceSelection(quotes=[EvidenceQuote(record_id="invented", text=records[0].content)])
    monkeypatch.setattr(service.llm, "select_evidence", wrong_id)
    assert not indexed_client.post("/api/knowledge/answer", json={"query":"processing fee"}).json()["grounded"]


def test_provider_errors_do_not_leak_secret_or_query(indexed_client, monkeypatch):
    service = indexed_client.app.state.knowledge
    async def broken(text):
        raise RuntimeError("secret-token customer@example.invalid")
    monkeypatch.setattr(service.embedding, "embed_query", broken)
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("darwix")
    logger.addHandler(handler)
    try:
        response = indexed_client.post("/api/knowledge/search", json={"query":"customer@example.invalid"})
    finally:
        logger.removeHandler(handler)
    assert "secret-token" not in response.text and "customer@example.invalid" not in response.text
    assert "RuntimeError" in stream.getvalue()
    assert "secret-token" not in stream.getvalue() and "customer@example.invalid" not in stream.getvalue()


def test_global_exception_handler(client):
    @client.app.get("/test-error")
    def test_error():
        raise RuntimeError("private exception text")
    response = client.get("/test-error")
    assert response.status_code == 500 and "private exception text" not in response.text
    assert response.json()["request_id"] == response.headers["x-request-id"]
