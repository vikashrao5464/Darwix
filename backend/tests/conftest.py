import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.knowledge.pipeline import load_manifest
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        qdrant_url="", qdrant_path=":memory:", embedding_provider="hash", llm_provider="extractive",
        normalized_dir=tmp_path / "normalized", recordings_dir=tmp_path / "recordings", provider_timeout_seconds=1,
        asr_provider="windows", asr_timeout_seconds=1)


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def indexed_client(client, settings):
    response = client.post("/api/knowledge/ingest", json={"paths": [entry.path for entry in load_manifest(settings)], "version": "1.0"})
    assert response.status_code == 200
    assert response.json()["status"] == "success", response.json()
    assert response.json()["indexed_records"] >= 10
    return client
