import argparse
import asyncio
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings
from app.knowledge.index import KnowledgeIndex
from app.knowledge.pipeline import IngestionPipeline
from app.knowledge.retrieve import KnowledgeService
from app.logging_config import configure_logging
from app.providers.embeddings import create_embedding_provider
from app.providers.llm import create_llm_provider
from app.schemas.knowledge import SearchRequest


async def evaluate(args):
    settings = Settings()
    configure_logging(settings.log_level)
    embedding, llm = create_embedding_provider(settings), create_llm_provider(settings)
    index = KnowledgeIndex(settings, embedding)
    try:
        try:
            await asyncio.wait_for(index.ensure(), settings.provider_timeout_seconds)
        except Exception as exc:
            logging.getLogger("darwix.evaluation").error("index_initialization_failed", extra={"error_type": type(exc).__name__})
            print(json.dumps({"status": "failed", "error": "qdrant_unavailable", "manual_action": "Start Docker Qdrant or select embedded mode; retry."}))
            return 1
        service = KnowledgeService(settings, embedding, llm, index, IngestionPipeline(settings, embedding, index))
        cases = json.loads((ROOT / "evaluations/retrieval/cases.json").read_text(encoding="utf-8"))
        results = []
        for case in cases:
            request = SearchRequest(query=case["query"], product=case.get("product", "business_loan"), language=case.get("language", "en"))
            retrieved = await service.search(request)
            answer = await service.answer(request)
            matching = [record for record in retrieved.records if record.document_id == case.get("expected_document_id")
                        and record.source_section == case.get("expected_section") and record.category == case["expected_category"]]
            if not case["expect_grounded"]:
                passed = not retrieved.grounded and not answer.grounded and not answer.citations and retrieved.reason == "insufficient_evidence"
                verdict = "correct" if passed else "incorrect"
                explanation = "Insufficient evidence produced a fallback." if passed else "Unsupported query was answered or provider failed."
            else:
                cited_ids = {c.record_id for c in answer.citations}
                direct = bool(matching and retrieved.records[0].record_id == matching[0].record_id
                              and matching[0].record_id in cited_ids and answer.grounded
                              and all(term.casefold() in answer.answer.casefold() for term in case["expected_terms"]))
                verdict = "correct" if direct else "partially_correct" if matching else "incorrect"
                explanation = "Expected source/section ranked first, supplied required facts and was cited." if direct else "Expected topic found, but rank, grounding, citation or answer coverage was incomplete." if matching else "Expected source/section was absent from top-k."
            results.append({**case, "retrieved_records": [record.model_dump(mode="json") for record in retrieved.records],
                            "answer": answer.model_dump(mode="json"), "relevance_explanation": explanation, "verdict": verdict})
        report = {"generated_at": datetime.now(timezone.utc).isoformat(), "embedding_provider": embedding.signature,
                  "answer_provider": settings.llm_provider, "threshold": settings.retrieval_min_score,
                  "collection": index.alias, "sample_count": len(results), "verdict_counts": dict(Counter(r["verdict"] for r in results)), "results": results}
        output = ROOT / "evaluations/retrieval/results.json"
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        lines = ["# Q2 retrieval evaluation", "", "Generated from actual Qdrant retrieval and answer output; synthetic demo data only.", "",
                 f"Embedding adapter: `{embedding.signature}`. Answer adapter: `{settings.llm_provider}`. Evidence threshold: {settings.retrieval_min_score}. Samples: {len(results)}.", "",
                 "Verdicts check source, section, category, rank, required facts, citations and the fallback. This small fixture set is not a general accuracy benchmark.", "",
                 "| Case / query | Expected topic | Top source / section | Score | Grounded answer | Verdict | Explanation |",
                 "|---|---|---|---|---|---|---|"]
        for result in results:
            top = result["retrieved_records"][0] if result["retrieved_records"] else None
            source = f"{top['source']} / {top['source_section']}" if top else "No results"
            score = f"{top['score']:.4f}" if top else "—"
            query = result["query"].replace("|", "\\|")
            lines.append(f"| {result['case_id']}: {query} | {result['expected_category']} | {source} | {score} | {result['answer']['grounded']} | {result['verdict']} | {result['relevance_explanation']} |")
        lines += ["", f"Actual verdict counts: `{report['verdict_counts']}`.", "", "Full returned records, source/page/version, scores and answers: [results.json](../evaluations/retrieval/results.json).", "",
                  "Hash embeddings are a lexical vector baseline and can miss short or semantic paraphrases. Hosted adapters were not exercised with live credentials unless the report provider fields say otherwise.", ""]
        (ROOT / "docs").mkdir(parents=True, exist_ok=True)
        (ROOT / "docs/q2-retrieval-evaluation.md").write_text("\n".join(lines), encoding="utf-8")
        print(json.dumps({"sample_count": len(results), "verdict_counts": report["verdict_counts"], "results": str(output.relative_to(ROOT))}))
        return 0 if all(r["verdict"] == "correct" for r in results) else 1
    finally:
        await index.close()
        await embedding.close()
        await llm.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate the existing index; run ingest --rebuild first.")
    sys.exit(asyncio.run(evaluate(parser.parse_args())))
