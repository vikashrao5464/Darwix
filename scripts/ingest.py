import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings
from app.knowledge.index import KnowledgeIndex
from app.knowledge.pipeline import IngestionPipeline
from app.logging_config import configure_logging
from app.providers.embeddings import create_embedding_provider


async def run(args):
    settings = Settings()
    configure_logging(settings.log_level)
    embedding = create_embedding_provider(settings)
    index = KnowledgeIndex(settings, embedding)
    try:
        try:
            await asyncio.wait_for(index.ensure(), settings.provider_timeout_seconds)
        except Exception as exc:
            logging.getLogger("darwix.ingest").error("index_initialization_failed", extra={"error_type": type(exc).__name__})
            print(json.dumps({"status": "failed", "error": "qdrant_unavailable", "manual_action": "Start Docker Qdrant or select embedded mode; retry."}))
            return 1
        report = await IngestionPipeline(settings, embedding, index).run(rebuild=args.rebuild)
        print(report.model_dump_json(indent=2))
        return 1 if report.status == "failed" else 0
    finally:
        await index.close()
        await embedding.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest the manifest; --rebuild replaces the complete demo index after validation.")
    parser.add_argument("--rebuild", action="store_true")
    sys.exit(asyncio.run(run(parser.parse_args())))
