"""Build a unified evidence summary from recorded results, without inventing verdicts."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def summarize():
    suites=ET.parse(ROOT/'evaluations/final-tests.xml').getroot().findall('.//testsuite')
    tests={key:sum(int(s.get(key,0)) for s in suites) for key in ['tests','failures','errors','skipped']}
    retrieval=read('evaluations/retrieval/results.json');q3=read('evaluations/localization/results.json');q4=read('evaluations/realtime/results.json')
    report={'backend_tests':tests,'retrieval':{'sample_count':retrieval['sample_count'],'verdict_counts':retrieval['verdict_counts']},
        'localization':{'scripted_calls_passed':q3['scripted_checks_passed'],'speech_probes':len(q3['speech_probes']),
            'intended_behaviors':sum(p['intended_behavior_reached'] for p in q3['speech_probes'])},
        'realtime':{'passed':q4['passed'],'runs':len(q4['runs']),'latency_samples':read('evaluations/realtime/latency.json')['sample_count']},
        'manual_remaining':['Native-speaker/compliance review','Consented human calls per market and broader accent/noise testing','Real contact coordination','Owner submission/publication and any exposed-key rotation']}
    output=ROOT/'evaluations/final-summary.json';output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    lines=['# Unified evaluation summary','','Generated from the stored JUnit and actual provider/replay reports.','','| Area | Observed result | Evidence |','|---|---|---|',
        f"| Backend | {tests['tests']} tests; {tests['failures']} failures; {tests['errors']} errors | [JUnit](../evaluations/final-tests.xml) |",
        '| Q1 | Three scripted recorded calls; actual Chrome speech/tools regression | [Q1](q1-results.md), [Chrome](../evaluations/voice/browser-smoke.json) |',
        f"| Q2 | {retrieval['sample_count']} queries; {retrieval['verdict_counts']} | [retrieval](q2-retrieval-evaluation.md) |",
        f"| Q3 | Scripted calls pass: {q3['scripted_checks_passed']}; {report['localization']['intended_behaviors']}/{len(q3['speech_probes'])} intended synthetic speech behaviors | [localization](q3-localization-report.md) |",
        f"| Q4 | {len(q4['runs'])} observed runs; passed: {q4['passed']}; {report['realtime']['latency_samples']} acknowledged samples | [real-time report](q4-latency-report.md), [video](../evaluations/realtime/live-demo.webm) |",
        '', 'Synthetic evidence and mocked hosted contracts do not certify human accuracy, native naturalness, compliance or production scale. Known retrieval and Filipino/Taglish speech failures are retained.','',
        'Manual remaining: '+ '; '.join(report['manual_remaining'])+'. See [checklist](submission-checklist.md).']
    (ROOT/'docs/evaluation-summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report))
if __name__=='__main__':summarize()
