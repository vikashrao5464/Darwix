"""Generate percentiles from acknowledged, persisted Q4 samples only."""
import argparse
import json
import sys
from pathlib import Path
from sqlalchemy import select
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.db.models import LatencySample
from app.db.session import initialize_database
from app.realtime.latency import summarize

def collect(call_ids=None):
    engine,sessions=initialize_database(Settings().database_url)
    try:
        with sessions() as session:
            query=select(LatencySample)
            if call_ids:query=query.where(LatencySample.call_id.in_(call_ids))
            return [{col.name:getattr(row,col.name) for col in row.__table__.columns if col.name!='sample_id'} for row in session.scalars(query)]
    finally:engine.dispose()
def write(samples,path):
    report={**summarize(samples),'samples':samples,
        'clock':'Server monotonic milliseconds from warmed replay start; model warmup excluded.',
        'delivery_definition':'Nudge stage complete to first observer acknowledgement; includes observer processing and return trip.',
        'nudge_definition':'llm_latency_ms is deterministic nudge construction time. Optional semantic classification belongs to signal time.',
        'buffering':'Chunk capture adds up to REALTIME_CHUNK_SECONDS before audio_received_ms; reported pipeline latency excludes this capture interval.'}
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--call-id',action='append')
    parser.add_argument('--output',default='evaluations/realtime/latency.json');args=parser.parse_args()
    report=write(collect(args.call_id),ROOT/args.output)
    print(json.dumps({'sample_count':report['sample_count'],'metrics':report['metrics']}))
    sys.exit(0 if report['sample_count'] else 1)
