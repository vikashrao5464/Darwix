import hashlib
import math
from abc import ABC, abstractmethod

from openai import AsyncOpenAI

from app.config import Settings
from app.knowledge.clean import query_tokens


class EmbeddingProvider(ABC):
    dimensions: int
    signature: str

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...

    async def close(self):
        pass


class HashEmbeddingProvider(EmbeddingProvider):
    """Offline vector baseline; feature hashing, not a trained semantic model."""
    def __init__(self, dimensions=512, terminology=None):
        self.dimensions = dimensions
        self.terminology = terminology or {}
        mapping_hash = hashlib.sha256(str(sorted(self.terminology.items())).encode()).hexdigest()[:12]
        self.signature = f"hash-v2:{dimensions}:{mapping_hash}"

    def vector(self, text, title=None):
        vector = [0.0] * self.dimensions
        for token in set(query_tokens(text, self.terminology)):
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1.0
        # Keep ranking within cosine vector retrieval. Heading terms carry
        # extra weight so incidental body mentions do not outrank the topic.
        for token in set(query_tokens(title or "", self.terminology)):
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 2.0
        length = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / length for x in vector]

    async def embed_documents(self, texts):
        return [self.vector(text, text.split("\n", 1)[0] if "\n" in text else None) for text in texts]

    async def embed_query(self, text):
        return self.vector(text)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings):
        self.dimensions = settings.embedding_dimensions
        self.model = settings.embedding_model
        self.signature = f"openai:{self.model}:{self.dimensions}"
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.openai_base_url,
            timeout=settings.provider_timeout_seconds, max_retries=0,
        )

    async def embed_documents(self, texts):
        response = await self.client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dimensions
        )
        return [row.embedding for row in sorted(response.data, key=lambda row: row.index)]

    async def embed_query(self, text):
        return (await self.embed_documents([text]))[0]

    async def close(self):
        await self.client.close()


def create_embedding_provider(settings):
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(settings)
    return HashEmbeddingProvider(settings.embedding_dimensions, settings.terminology())
