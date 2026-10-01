import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import Settings
from app.providers.embeddings import HashEmbeddingProvider, OpenAIEmbeddingProvider
from app.providers.llm import EvidenceQuote, EvidenceSelection, OpenAILLMProvider
from app.schemas.retrieval import RetrievedRecord
from app.schemas.voice import InterpretedTurn


def test_hash_vectors_reproducible_and_heading_weighted():
    async def run():
        provider = HashEmbeddingProvider(512)
        query = await provider.embed_query("processing fee")
        documents = await provider.embed_documents(["Processing fees\nThe fee is 2 percent.", "Other topic\nA processing fee is mentioned in this long unrelated paragraph about checks, identity and documents."])
        assert query == await provider.embed_query("processing fee")
        assert sum(x * y for x, y in zip(query, documents[0])) > sum(x * y for x, y in zip(query, documents[1]))
    asyncio.run(run())


def test_configuration_requires_key_and_validates_chunk_overlap():
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(_env_file=None, llm_provider="openai", openai_api_key="")
    with pytest.raises(ValidationError, match="overlap"):
        Settings(_env_file=None, chunk_words=50, chunk_overlap_words=50)


def test_openai_embeddings_wire_contract_without_network(settings):
    async def run():
        provider = OpenAIEmbeddingProvider(settings.model_copy(update={"openai_api_key": settings.openai_api_key.__class__("test-placeholder")}))
        await provider.client.close()
        requests = []
        def handler(request):
            assert request.url.path == "/v1/embeddings"
            body = json.loads(request.content)
            requests.append(body)
            return httpx.Response(200, json={"object":"list", "model":body["model"], "data":[
                {"object":"embedding", "index":i, "embedding":[0.1] * settings.embedding_dimensions}
                for i in reversed(range(len(body["input"])))], "usage":{"prompt_tokens":1,"total_tokens":1}})
        provider.client = AsyncOpenAI(api_key="test-placeholder", max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        try:
            assert len(await provider.embed_documents(["First redacted document", "Second redacted document"])) == 2
            assert len(await provider.embed_query("query")) == settings.embedding_dimensions
            assert requests[0]["dimensions"] == settings.embedding_dimensions
            assert requests[1]["input"] == ["query"]
        finally:
            await provider.close()
    asyncio.run(run())


def test_openai_llm_receives_only_retrieved_context_and_strict_schema(settings, monkeypatch):
    async def run():
        configured = settings.model_copy(update={"openai_api_key": settings.openai_api_key.__class__("test-placeholder")})
        provider = OpenAILLMProvider(configured)
        record = RetrievedRecord(record_id="fixture_record", document_id="fixture", title="Fee", content="Processing fee is 2 percent.",
            category="policy", product="business_loan", source="fixture.md", source_type="markdown", version="1.0",
            contains_pii=False, language="en", checksum="sha256:fixture", score=0.9)
        async def parse(**kwargs):
            assert kwargs["store"] is False
            assert kwargs["text_format"] is EvidenceSelection
            body = json.loads(kwargs["input"][1]["content"])
            assert body == {"query":"processing fee", "context":[{"record_id":record.record_id,"content":record.content}]}
            assert "Use only" in kwargs["input"][0]["content"]
            return SimpleNamespace(output_parsed=EvidenceSelection(quotes=[EvidenceQuote(record_id=record.record_id, text=record.content)]))
        monkeypatch.setattr(provider.client.responses, "parse", parse)
        try:
            selected = await provider.select_evidence("processing fee", [record])
            assert selected.quotes[0].text == record.content
        finally:
            await provider.close()
    asyncio.run(run())


def test_openai_voice_interpretation_contract_and_refusal(settings, monkeypatch):
    async def run():
        provider=OpenAILLMProvider(settings.model_copy(update={"openai_api_key":settings.openai_api_key.__class__("test-placeholder")}))
        async def parse(**kwargs):
            assert kwargs["store"] is False and kwargs["text_format"] is InterpretedTurn
            assert json.loads(kwargs["input"][1]["content"]) == {"text":"500000","pending_field":"requested_amount"}
            prompt=kwargs["input"][0]["content"]
            assert "search_knowledge" in prompt and "preliminary" in prompt and "exact evidence" in prompt
            return SimpleNamespace(output_parsed=InterpretedTurn(intent="details",field="requested_amount",evidence="500000",uncertain=False))
        monkeypatch.setattr(provider.client.responses,"parse",parse)
        try:
            assert (await provider.interpret_turn("500000","requested_amount")).field == "requested_amount"
            async def refused(**kwargs): return SimpleNamespace(output_parsed=None)
            monkeypatch.setattr(provider.client.responses,"parse",refused)
            with pytest.raises(ValueError,match="unavailable"):
                await provider.interpret_turn("500000","requested_amount")
        finally:
            await provider.close()
    asyncio.run(run())
