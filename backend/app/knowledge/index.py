import hashlib
import logging
import uuid

from qdrant_client import AsyncQdrantClient, models

from app.config import ROOT
from app.schemas.knowledge import KnowledgeRecord
from app.schemas.retrieval import RetrievedRecord

logger = logging.getLogger("darwix.index")


class KnowledgeIndex:
    def __init__(self, settings, embedding):
        self.dimensions = embedding.dimensions
        self.alias = settings.qdrant_collection + "_" + hashlib.sha256(embedding.signature.encode()).hexdigest()[:12]
        if settings.qdrant_url:
            self.client = AsyncQdrantClient(url=settings.qdrant_url,
                api_key=settings.qdrant_api_key.get_secret_value() or None,
                timeout=settings.provider_timeout_seconds)
        elif settings.qdrant_path == ":memory:":
            self.client = AsyncQdrantClient(location=":memory:")
        else:
            path = ROOT / settings.qdrant_path
            path.mkdir(parents=True, exist_ok=True)
            self.client = AsyncQdrantClient(path=str(path))

    async def _active_collection(self):
        return next((a.collection_name for a in (await self.client.get_aliases()).aliases if a.alias_name == self.alias), None)

    async def ensure(self):
        if await self._active_collection() is None:
            name = self.alias + "_" + uuid.uuid4().hex
            await self.client.create_collection(name, vectors_config=models.VectorParams(size=self.dimensions, distance=models.Distance.COSINE))
            await self.client.update_collection_aliases([
                models.CreateAliasOperation(create_alias=models.CreateAlias(collection_name=name, alias_name=self.alias))
            ])

    async def snapshot(self):
        points, offset = [], None
        while True:
            batch, offset = await self.client.scroll(self.alias, limit=256, offset=offset, with_payload=True, with_vectors=True)
            points.extend(batch)
            if offset is None:
                return points

    async def replace(self, records, vectors, rebuild=False, document_ids=None):
        if len(records) != len(vectors):
            raise ValueError("embedding_count_mismatch")
        if any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError("embedding_dimension_mismatch")
        previous = await self._active_collection()
        retained = [] if rebuild else [p for p in await self.snapshot() if p.payload["document_id"] not in (document_ids or set())]
        points = [models.PointStruct(id=p.id, vector=p.vector, payload=p.payload) for p in retained]
        points.extend(models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, record.record_id)), vector=vector,
                                        payload=record.model_dump(mode="json")) for record, vector in zip(records, vectors))
        staging = self.alias + "_" + uuid.uuid4().hex
        switched = False
        try:
            await self.client.create_collection(staging, vectors_config=models.VectorParams(size=self.dimensions, distance=models.Distance.COSINE))
            if points:
                await self.client.upsert(staging, points, wait=True)
            count = (await self.client.count(staging, exact=True)).count
            if count != len(points):
                raise ValueError("index_count_mismatch")
            operations = []
            if previous:
                operations.append(models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=self.alias)))
            operations.append(models.CreateAliasOperation(create_alias=models.CreateAlias(collection_name=staging, alias_name=self.alias)))
            # Qdrant switches aliases atomically after the staging snapshot is complete.
            await self.client.update_collection_aliases(operations)
            switched = True
        finally:
            if not switched:
                try:
                    await self.client.delete_collection(staging)
                except Exception as exc:
                    logger.warning("staging_cleanup_failed", extra={"error_type": type(exc).__name__})
        if previous:
            try:
                await self.client.delete_collection(previous)
            except Exception as exc:
                logger.warning("old_collection_cleanup_failed", extra={"error_type": type(exc).__name__})
        return count

    async def search(self, vector, product, language, top_k):
        result = await self.client.query_points(
            self.alias, query=vector, limit=top_k, with_payload=True,
            query_filter=models.Filter(must=[
                models.FieldCondition(key="product", match=models.MatchValue(value=product)),
                models.FieldCondition(key="language", match=models.MatchValue(value=language)),
            ]),
        )
        return [RetrievedRecord(**point.payload, score=point.score) for point in result.points]

    async def records(self):
        return [KnowledgeRecord(**point.payload) for point in await self.snapshot()]

    async def close(self):
        await self.client.close()
