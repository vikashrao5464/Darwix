import asyncio
import uuid
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from app.realtime.replay import catalogue, public_audio
from app.schemas.realtime import ReplayRequest

router=APIRouter(tags=['realtime'])
@router.get('/api/realtime/fixtures')
async def fixtures():
    return catalogue()
@router.get('/api/realtime/fixtures/{fixture_id}/audio')
async def fixture_audio(fixture_id:str):
    entry=next((e for e in catalogue() if e['fixture_id']==fixture_id),None)
    if not entry or not public_audio(entry).is_file(): raise HTTPException(404,'Demo recording unavailable.')
    return FileResponse(public_audio(entry),media_type='audio/wav',headers={'Cache-Control':'no-store'})
@router.post('/api/realtime/replays',status_code=201)
async def start_replay(body:ReplayRequest,request:Request):
    entry=next((e for e in catalogue() if e['fixture_id']==body.fixture_id),None)
    if not entry or not public_audio(entry).is_file(): raise HTTPException(404,'Demo recording unavailable.')
    try: job=request.app.state.realtime.start(entry,body.call_id or 'replay_'+uuid.uuid4().hex)
    except ValueError as exc: raise HTTPException(409,str(exc)) from None
    return job.info()
def job_for(manager,call_id):
    job=manager.jobs.get(call_id)
    if not job: raise HTTPException(404,'Replay not available in this backend session. Start a new replay.')
    return job
@router.get('/api/realtime/replays/{call_id}')
async def snapshot(call_id:str,request:Request):
    return job_for(request.app.state.realtime,call_id).snapshot()
@router.post('/api/realtime/replays/{call_id}/stop')
async def stop(call_id:str,request:Request):
    job=job_for(request.app.state.realtime,call_id)
    if job.task and not job.task.done():
        job.task.cancel(); await asyncio.gather(job.task,return_exceptions=True)
    return job.info()
@router.websocket('/ws/calls/{call_id}')
async def events(websocket:WebSocket,call_id:str):
    origin=websocket.headers.get('origin')
    if origin and origin not in websocket.app.state.settings.cors_origins:
        await websocket.close(code=1008); return
    job=websocket.app.state.realtime.jobs.get(call_id)
    if not job: await websocket.close(code=1008); return
    try: queue=job.hub.subscribe()
    except RuntimeError: await websocket.close(code=1013); return
    async def sender():
        while True:
            event=await queue.get()
            if event['type']=='disconnect': await websocket.close(code=1013); return
            await websocket.send_json(event)
    async def receiver():
        while True:
            text=await websocket.receive_text()
            if len(text)>1024: await websocket.close(code=1009); return
            import json
            try: message=json.loads(text)
            except ValueError: await websocket.close(code=1003); return
            if not isinstance(message,dict): await websocket.close(code=1003); return
            if message.get('type')=='ack' and type(message.get('chunk_id')) is int:
                await job.acknowledge(message['chunk_id'])
    tasks=[]
    try:
        await websocket.accept()
        await websocket.send_json({'type':'snapshot','payload':job.snapshot()})
        tasks=[asyncio.create_task(sender()),asyncio.create_task(receiver())]
        await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
    except (WebSocketDisconnect, asyncio.CancelledError): pass
    finally:
        job.hub.unsubscribe(queue)
        for task in tasks: task.cancel()
        try: await asyncio.gather(*tasks,return_exceptions=True)
        except asyncio.CancelledError: pass
