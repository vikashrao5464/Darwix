from fastapi import APIRouter, HTTPException, Request

from app.schemas.knowledge import IngestionReport, IngestRequest, SearchRequest
from app.schemas.retrieval import AnswerResult, RetrievalResult

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/ingest", response_model=IngestionReport)
async def ingest(body: IngestRequest, request: Request):
    try:
        return await request.app.state.knowledge.pipeline.run(body.paths, body.version)
    except ValueError:
        raise HTTPException(status_code=400, detail="Sources must be registered in the configured manifest.") from None


@router.post("/search", response_model=RetrievalResult)
async def search(body: SearchRequest, request: Request):
    return await request.app.state.knowledge.search(body)


@router.post("/answer", response_model=AnswerResult)
async def answer(body: SearchRequest, request: Request):
    return await request.app.state.knowledge.answer(body)
