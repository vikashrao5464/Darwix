from fastapi import APIRouter, Request

from app.schemas.voice import CallbackRequest

router = APIRouter(tags=["callbacks"])


@router.post("/api/callbacks")
@router.post("/api/voice/tools/schedule_callback")
async def callback(body: CallbackRequest, request: Request):
    return request.app.state.voice_tools.schedule_callback(body)
