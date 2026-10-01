from typing import Protocol

from app.schemas.voice import CallCreate, CallReply, TurnRequest


class VoiceProvider(Protocol):
    async def start_call(self, request: CallCreate) -> CallReply: ...
    async def process_turn(self, call_id: str, request: TurnRequest) -> CallReply: ...
    async def end_call(self, call_id: str) -> dict: ...


class BrowserVoiceProvider:
    """Browser transport delegates all business decisions to the shared controller."""
    def __init__(self, conversation):
        self.conversation = conversation

    async def start_call(self, request):
        return self.conversation.start_call(request)

    async def process_turn(self, call_id, request):
        return await self.conversation.turn(call_id, request)

    async def end_call(self, call_id):
        return self.conversation.end_call(call_id)
