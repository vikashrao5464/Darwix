from fastapi import APIRouter, Request

from app.schemas.knowledge import SearchRequest
from app.schemas.voice import CallCreate, CallReference, ConsentRequest, QualificationUpdate, TurnRequest

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/calls")
async def start_call(body: CallCreate, request: Request):
    return await request.app.state.voice.start_call(body)


@router.get("/calls/{call_id}")
async def get_call(call_id: str, request: Request):
    return request.app.state.conversation.snapshot(call_id)


@router.post("/calls/{call_id}/turn")
async def turn(call_id: str, body: TurnRequest, request: Request):
    return await request.app.state.voice.process_turn(call_id, body)


@router.post("/calls/{call_id}/end")
async def end_call(call_id: str, request: Request):
    return await request.app.state.voice.end_call(call_id)


@router.post("/consent")
async def consent(body: ConsentRequest, request: Request):
    return request.app.state.voice_tools.consent(body)


@router.post("/qualification")
@router.post("/tools/update_qualification")
async def qualification(body: QualificationUpdate, request: Request):
    return request.app.state.voice_tools.update_qualification(body)


@router.post("/eligibility")
@router.post("/tools/evaluate_preliminary_eligibility")
async def eligibility(body: CallReference, request: Request):
    return await request.app.state.voice_tools.eligibility(body.call_id)


@router.post("/tools/search_knowledge")
async def search_knowledge(body: SearchRequest, request: Request):
    return await request.app.state.voice_tools.search_knowledge(body)
