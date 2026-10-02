"""Compare recorded streamed events with independently defined fixture expectations."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from summarize_latency import collect,write

def evaluate(paths):
    cases=[];calls=[]
    source=json.loads((ROOT/'evaluations/realtime/q1_insights-source.json').read_text(encoding='utf-8'))
    for path in paths:
        observed=json.loads(path.read_text(encoding='utf-8'));snapshot=observed['snapshot'];call=snapshot['call_id'];calls.append(call)
        signals={};current=None;nudge_during=False;transcript_during=False;seen_status='preparing'
        for event in observed['events']:
            if 'payload' not in event or event.get('type') not in {'snapshot','status','transcript','signal','nudge','suppressed','latency','chunk_complete','warning'}: continue
            payload=event['payload'];kind=event['type']
            if kind in {'status','snapshot'}:seen_status=payload['status']
            if kind=='transcript':
                current=payload['chunk_id'];signals.setdefault(current,set())
                if seen_status=='replaying':transcript_during=True
            if kind=='signal' and current is not None:signals[current].add(payload['type'])
            if kind=='nudge' and seen_status=='replaying' and payload['created_at_ms']<snapshot['duration_ms']:nudge_during=True
        expected={e['chunk_id']:set(e['types']) for e in source['expected']} if snapshot['fixture_id']=='q1_insights' else {}
        comparison=[];tp=fp=fn=0
        for chunk in sorted(set(signals)|set(expected)):
            wanted=expected.get(chunk,set());actual=signals.get(chunk,set())
            tp+=len(wanted&actual);fp+=len(actual-wanted);fn+=len(wanted-actual)
            comparison.append({'chunk_id':chunk,'expected':sorted(wanted),'emitted':sorted(actual),
                'false_positive':sorted(actual-wanted),'false_negative':sorted(wanted-actual)})
        suppression=snapshot['suppression'];reasons={e['reason'] for e in suppression}
        quality={'observer':observed['observer'],'call_id':call,'fixture_id':snapshot['fixture_id'],
            'status':snapshot['status'],'true_positives':tp,'false_positives':fp,'false_negatives':fn,
            'transcript_before_playback_end':transcript_during,'nudge_before_playback_end':nudge_during,
            'duration_ms':snapshot['duration_ms'],'playback_finished_ms':snapshot['playback_finished_ms'],
            'duplicate_suppressed':'duplicate' in reasons,'ambiguous_suppressed':'low_confidence' in reasons,
            'counts':snapshot['counts'],'comparison':comparison,'suppression':suppression,
            'event_file':path.relative_to(ROOT).as_posix()}
        quality['passed']=snapshot['status']=='completed' and transcript_during and fp==0 and fn==0
        if snapshot['fixture_id']=='q1_insights': quality['passed'] &= nudge_during and quality['duplicate_suppressed'] and quality['ambiguous_suppressed']
        cases.append(quality)
    report={'runs':cases,'passed':bool(cases) and all(c['passed'] for c in cases),
        'scope':'Tiny synthesized English fixture set. Per-chunk signal FP/FN, not a human-call accuracy benchmark. Ground-truth text is not supplied to ASR/detector.'}
    output=ROOT/'evaluations/realtime';output.mkdir(parents=True,exist_ok=True)
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    latency=write(collect(calls),output/'latency.json')
    lines=['# Q4 real-time observations and latency','','Generated from real clock-paced recordings, local Whisper inference and observer acknowledgements.','',
        '## Executed replay runs','','| Recording / observer | TP / FP / FN | Playback seconds | Transcript / nudge before end | Duplicate / weak withheld | Verdict |', '|---|---|---|---|---|---|']
    for c in cases:
        playback=round(c['playback_finished_ms']/1000,3) if c['playback_finished_ms'] is not None else None
        lines.append(f"| {c['fixture_id']} / {c['observer']} | {c['true_positives']} / {c['false_positives']} / {c['false_negatives']} | {playback} / {c['duration_ms']/1000} | {c['transcript_before_playback_end']} / {c['nudge_before_playback_end']} | {c['duplicate_suppressed']} / {c['ambiguous_suppressed']} | {'pass' if c['passed'] else 'fail'} |")
    lines += ['',report['scope'],'','Full transcript/events and per-window errors: [JSON](../evaluations/realtime/results.json). The original Q1 cooperative call is a negative control; no nudge is expected. The Q1 stress call reuses its actual opening and adds explicitly synthetic risky-agent/objection phrases, noise and duplicate windows. Unsafe lines are deliberate evaluation injections, not assistant policy or ordinary controller output.','',
        '## Measured pipeline latency','',f"Acknowledged sample count: **{latency['sample_count']}**.",'','| Stage | P50 ms | P95 ms |','|---|---|---|']
    for key,values in latency['metrics'].items():lines.append(f"| {key} | {values['p50_ms']} | {values['p95_ms']} |")
    lines += ['','Definitions: '+latency['clock']+' '+latency['buffering'],'',latency['delivery_definition']+' '+latency['nudge_definition'],
        '', 'Client labels distinguish rendered Chrome acknowledgements from CLI receipt acknowledgements. Unacknowledged samples are omitted from percentiles and counted; no zero-delivery substitute is inserted. Persisted samples: [JSON](../evaluations/realtime/latency.json). These observations are not production service-level objectives.', '',
        '## Implementation and limitations','','- Six-second fixed chunks are read at real-time speed; only a WAV header and sidecar role/timing metadata are read upfront. Whisper remains warm for the replay, and final chunk transcripts are analyzed continuously. No reference words are given to recognition or detection.',
        '- The local adapter emits final chunk text, not token-level partial transcripts. Word boundaries across chunks can lose context. No diarization: registered synthetic role annotations label single-role chunks; mixed-role or unannotated chunks remain unknown and do not produce role-dependent signals.',
        '- Rolling context, bounded ASR queue, one active replay, bounded subscribers, provider timeouts and cancellation prevent unbounded accumulation. Overload/ASR failure stops analysis safely instead of claiming timely completion.',
        '- Default signals use conservative rules and configured thresholds. The optional structured LLM classifier is opt-in, exact-evidence checked, timeout-protected and covered by mocked tests; no live hosted classifier was measured. Confidence scores are heuristics, not calibrated probabilities.',
        '- Priority, cooldown, normalized evidence/action fingerprints and expiry suppress noise and duplicate nudges. Dashboard nudges expire; guidance performs no lead/payment/contract action. Weak or unclear recognition produces no signal.',
        '- Expand evaluation to consented human calls, accents, noisy finance speech and real semantic-classifier runs before deployment. Six-second capture delay and measured inference time make this a chunked prototype.',
        '', '## Reproduction','','```powershell',r'.\.venv\Scripts\python.exe scripts/create_realtime_fixtures.py',r'.\.venv\Scripts\python.exe scripts/replay_audio.py --file data/audio/q4/q1_insights.wav --output evaluations/realtime/cli-insights.json',
        r'.\.venv\Scripts\python.exe scripts/replay_audio.py --file data/audio/q1/cooperative.wav --output evaluations/realtime/cli-cooperative.json',
        'npm --prefix frontend run test:live',r'.\.venv\Scripts\python.exe scripts/evaluate_realtime.py',r'.\.venv\Scripts\python.exe scripts/summarize_latency.py','```','',
        'Chrome demo: [video](../evaluations/realtime/live-demo.webm). The recording includes a supported Q1 FAQ, unsupported-question fallback, and Q4 live nudges/suppression. See [submission checklist](submission-checklist.md) for remaining human validation.']
    (ROOT/'docs/q4-latency-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'runs':len(cases),'samples':latency['sample_count']}))
    return 0 if report['passed'] and latency['sample_count'] else 1
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--events',action='append');args=parser.parse_args()
    files=args.events or ['evaluations/realtime/cli-insights.json','evaluations/realtime/cli-cooperative.json','evaluations/realtime/browser-smoke.json']
    sys.exit(evaluate([ROOT/file for file in files]))
