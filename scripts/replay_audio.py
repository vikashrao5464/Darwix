"""Start a registered clock-paced replay; observe and acknowledge streamed results."""
import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path
import httpx
from websockets.asyncio.client import connect
ROOT=Path(__file__).resolve().parents[1]
async def replay(args):
    async with httpx.AsyncClient(base_url=args.base_url,timeout=30) as client:
        fixtures=(await client.get('/api/realtime/fixtures')).json()
        requested=(ROOT/args.file).resolve()
        entry=next((e for e in fixtures if (ROOT/e['audio']).resolve()==requested),None)
        if not entry: raise ValueError('File must be a registered public recording in data/fixtures/replays.json')
        response=await client.post('/api/realtime/replays',json={'fixture_id':entry['fixture_id'],'call_id':args.call_id})
        response.raise_for_status(); call=response.json()['call_id']; events=[]
        async with connect(args.base_url.replace('http','ws',1)+f'/ws/calls/{call}',open_timeout=10,max_size=1_000_000) as ws:
            async for text in ws:
                event=json.loads(text); events.append(event)
                if event['type']=='chunk_complete': await ws.send(json.dumps({'type':'ack','chunk_id':event['payload']['chunk_id']}))
                if event['type'] in {'nudge','suppressed','status'}: print(json.dumps(event),flush=True)
                if event['type'] in {'status','snapshot'} and event['payload']['status'] in {'completed','failed','stopped'}: break
        snapshot=(await client.get(f'/api/realtime/replays/{call}')).json()
        if args.output:
            path=ROOT/args.output;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps({'observer':'CLI receipt acknowledgement, not rendered UI','events':events,'snapshot':snapshot},indent=2)+'\n',encoding='utf-8')
        return 0 if snapshot['status']=='completed' else 1
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',required=True);parser.add_argument('--call-id',default='replay_'+uuid.uuid4().hex)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000');parser.add_argument('--output')
    try:sys.exit(asyncio.run(replay(parser.parse_args())))
    except Exception as exc:print(f'Replay failed: {type(exc).__name__}. Check services, recording registration and models.');sys.exit(1)
