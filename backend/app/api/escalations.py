from fastapi import APIRouter, Request

from app.schemas.voice import EscalationRequest

router = APIRouter(tags=["escalations"])


@router.post("/api/escalations")
@router.post("/api/voice/tools/request_human_escalation")
async def escalation(body: EscalationRequest, request: Request):
    return request.app.state.voice_tools.request_human_escalation(body)
