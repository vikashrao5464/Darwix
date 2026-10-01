import asyncio
import math


async def embed_records(records, provider, timeout):
    vectors = []
    for start in range(0, len(records), 64):
        batch = records[start:start + 64]
        result = await asyncio.wait_for(provider.embed_documents([
            record.title + "\n" + record.content for record in batch
        ]), timeout=timeout)
        if len(result) != len(batch) or any(len(v) != provider.dimensions or not all(math.isfinite(x) for x in v) for v in result):
            raise ValueError("invalid_embeddings")
        vectors.extend(result)
    return vectors
