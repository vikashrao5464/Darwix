from fastapi import APIRouter, Request

from app.schemas.voice import LeadRequest

router = APIRouter(tags=["leads"])


@router.post("/api/leads")
@router.post("/api/voice/tools/create_lead")
async def create_lead(body: LeadRequest, request: Request):
    return await request.app.state.voice_tools.create_lead(body)
