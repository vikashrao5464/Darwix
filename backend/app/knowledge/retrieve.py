import asyncio
import logging

from app.knowledge.citations import citation
from app.knowledge.clean import clean_text, query_tokens
from app.knowledge.pii import redact_pii
from app.schemas.retrieval import AnswerResult, RetrievalResult

logger = logging.getLogger("darwix.retrieval")
FALLBACK = "I don't have verified information for that in the available business knowledge base. I can connect you with a human representative."


class KnowledgeService:
    def __init__(self, settings, embedding, llm, index, pipeline):
        self.settings, self.embedding, self.llm, self.index, self.pipeline = settings, embedding, llm, index, pipeline

    async def search(self, request):
        query = clean_text(redact_pii(request.query, self.settings.government_id_patterns).redacted_text, self.settings.terminology())
        result = RetrievalResult(query=query)
        try:
            vector = await asyncio.wait_for(self.embedding.embed_query(query), self.settings.provider_timeout_seconds)
            result.records = await asyncio.wait_for(
                self.index.search(vector, request.product, request.language, request.top_k), self.settings.provider_timeout_seconds)
        except Exception as exc:
            logger.warning("retrieval_provider_failed", extra={"error_type": type(exc).__name__})
            result.reason = "provider_or_index_unavailable"
            return result
        # Hash vectors can collide. Require actual token evidence as well as cosine.
        evidence = self.evidence_records(result)
        result.grounded = bool(evidence)
        result.reason = None if evidence else "insufficient_evidence"
        # Keep low-scoring hits for traceable search; answer applies the same gate.
        return result

    def evidence_records(self, result):
        records = [record for record in result.records if record.score >= self.settings.retrieval_min_score]
        if self.settings.embedding_provider == "hash":
            tokens = set(query_tokens(result.query, self.settings.terminology()))
            records = [record for record in records if tokens and len(tokens & set(query_tokens(
                record.title + " " + record.content, self.settings.terminology()))) / len(tokens) >= 0.75]
        return records

    async def answer(self, request):
        result = await self.search(request)
        fallback = AnswerResult(answer=FALLBACK, grounded=False, mode=self.settings.llm_provider, reason=result.reason)
        if not result.grounded:
            return fallback
        records = self.evidence_records(result)
        try:
            selection = await asyncio.wait_for(self.llm.select_evidence(result.query, records), self.settings.provider_timeout_seconds)
            by_id = {record.record_id: record for record in records}
            if not selection.quotes or len(selection.quotes) > 2:
                fallback.reason = "answer_evidence_unavailable"
                return fallback
            # Reject hallucinated IDs and any new wording. The provider selects
            # evidence; the server renders only verified verbatim KB text.
            if any(quote.record_id not in by_id or len(quote.text.strip()) < 8 or
                   quote.text not in by_id[quote.record_id].content for quote in selection.quotes):
                fallback.reason = "invalid_provider_evidence"
                return fallback
            selected_records = list({quote.record_id: by_id[quote.record_id] for quote in selection.quotes}.values())
            prefix = "Synthetic demo information: " if any(record.synthetic for record in selected_records) else "Verified KB excerpt: "
            return AnswerResult(answer=prefix + " ".join(quote.text for quote in selection.quotes), grounded=True,
                citations=[citation(record) for record in selected_records], mode=self.settings.llm_provider)
        except Exception as exc:
            logger.warning("answer_provider_failed", extra={"error_type": type(exc).__name__})
            fallback.reason = "answer_provider_unavailable"
            return fallback
