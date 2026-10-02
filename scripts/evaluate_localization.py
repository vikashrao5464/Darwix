"""Observe real HTTP replies, synthesize four calls, and probe actual local ASR."""
import argparse
import asyncio
import io
import json
import re
import sys
import time
import wave
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.config import Settings
from app.providers.mms_tts import MMSTTSProvider
from app.providers.whisper_asr import WhisperASRProvider
from app.providers.windows_speech import WindowsSpeechProvider
from app.voice.audio import prepare_audio


def join_audio(parts, target):
    chunks = []
    timeline = []
    position = 0
    for speaker, text, data in parts:
        with wave.open(io.BytesIO(data)) as source:
            rate = source.getframerate()
            samples = np.frombuffer(source.readframes(source.getnframes()), dtype='<i2').astype(float)
        count = round(len(samples) * 16000 / rate)
        samples = np.interp(np.arange(count) * rate / 16000, np.arange(len(samples)), samples).astype('<i2')
        start = round(position / 16)
        chunks.append(samples.tobytes())
        position += count
        timeline.append({'speaker':speaker, 'text':text, 'start_ms':start, 'end_ms':round(position / 16)})
        chunks.append(bytes(16000))
        position += 8000
    with wave.open(str(target), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b''.join(chunks))
    return timeline


def word_errors(reference, observed):
    expected = re.findall(r'\w+', reference.casefold())
    actual = re.findall(r'\w+', observed.casefold())
    previous = list(range(len(actual) + 1))
    for index, word in enumerate(expected, 1):
        row = [index]
        for position, candidate in enumerate(actual, 1):
            row.append(min(row[-1] + 1, previous[position] + 1,
                           previous[position-1] + (word != candidate)))
        previous = row
    return {'edit_distance':previous[-1], 'reference_words':len(expected),
            'word_error_rate':round(previous[-1] / max(1,len(expected)),4)}


def check(reply, step):
    expected = step['expect']
    passed = bool(reply.get('grounded') and reply.get('citations')) if expected=='grounded' else (
        reply.get('grounded') is False and not reply.get('citations') if expected=='fallback' else
        bool(reply.get('callback_id')) if expected=='callback' else
        any(term in reply['text'] for term in ('Hindi ako', 'tidak bisa menjanjikan', 'nggak bisa janji')) if expected=='difficulty' else
        any(term in reply['text'] for term in ('Anong araw', 'hari apa', 'Hari dan jam')) if expected=='callback_prompt' else
        reply['status']==expected)
    if step.get('language'):
        passed = passed and reply['language_state']['preferred_response_language']==step['language']
    return passed


async def evaluate(base_url, without_audio, speech_only=False):
    output = ROOT / 'evaluations/localization'
    audio_dir = ROOT / 'data/audio/q3'
    audio_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings()
    previous_report = json.loads((output / 'results.json').read_text(encoding='utf-8')) if speech_only else None
    tts = MMSTTSProvider(settings, WindowsSpeechProvider(settings))
    cache = {}
    async def synthesize(text, language):
        key = (text, language)
        if key not in cache:
            cache[key] = await tts.synthesize(text, language)
        return cache[key]
    calls = previous_report['calls'] if speech_only else []
    async with httpx.AsyncClient(base_url=base_url, timeout=75) as client:
        async def post(path, body):
            response = await client.post(path, json=body)
            response.raise_for_status()
            return response.json()
        for scenario in ([] if speech_only else json.loads((output / 'scenarios.json').read_text(encoding='utf-8'))):
            reply = await post('/api/voice/calls', {'scenario':scenario['scenario'], 'response_language':scenario['language']})
            call_id = reply['call_id']
            observations = []
            parts = []
            if not without_audio:
                response = await client.get(f'/api/voice/calls/{call_id}/speech/greeting')
                response.raise_for_status()
                parts.append(('agent',reply['text'],response.content))
            for index, step in enumerate(scenario['turns']):
                started = time.perf_counter()
                reply = await post(f'/api/voice/calls/{call_id}/turn', {'turn_id':f'turn_{index}', 'text':step['text']})
                entry = {'input':step['text'], 'expected':step, 'reply':reply, 'passed':check(reply,step),
                         'request_ms':round((time.perf_counter()-started)*1000)}
                observations.append(entry)
                print(json.dumps({'scenario':scenario['id'], 'turn':index, 'passed':entry['passed']}), flush=True)
                if not without_audio:
                    language = reply['language_state']['preferred_response_language']
                    voice = 'id' if scenario['scenario']=='id_installment' else 'en' if language=='en' else 'fil'
                    parts.append(('customer', step['text'], await synthesize(step['text'], voice)))
                    response = await client.get(f'/api/voice/calls/{call_id}/speech/turn_{index}')
                    response.raise_for_status()
                    parts.append(('agent', reply['text'], response.content))
            item = {'id':scenario['id'], 'call_id':call_id, 'scenario':scenario['scenario'],
                'input_mode':'scripted text; not human microphone calls',
                'audio_kind':'synthesized from actual executed replies' if not without_audio else 'absent',
                'observations':observations, 'passed':all(item['passed'] for item in observations)}
            if parts:
                target = audio_dir / (scenario['id'] + '.wav')
                item['audio'] = target.relative_to(ROOT).as_posix()
                item['timeline'] = join_audio(parts,target)
            calls.append(item)
            (output / (scenario['id']+'.json')).write_text(json.dumps(item,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        probes = []
        if not without_audio:
            for name, scenario, language, text in (
                ('ph_english','ph_renewal','en','What is a premium?'),
                ('ph_filipino','ph_renewal','fil','Ano ang hulog?'),
                ('ph_taglish','ph_renewal','fil-en','Ano po ang premium?'),
                ('id_formal','id_installment','id-formal','Apa tenor itu?'),
                ('id_colloquial','id_installment','id-colloquial','Apa cicilan itu, aku nggak ngerti?'),
                ('id_mixed','id_installment','id-en-mixed','Apa down payment itu?'),
            ):
                reply = await post('/api/voice/calls', {'scenario':scenario,'response_language':language})
                call_id = reply['call_id']
                await post(f'/api/voice/calls/{call_id}/turn', {'turn_id':'consent','text':'Ya' if scenario=='id_installment' else 'Yes'})
                voice = 'id' if scenario=='id_installment' else 'en' if language=='en' else 'fil'
                target = audio_dir / ('probe_'+name+'.wav')
                data = target.read_bytes() if speech_only and target.is_file() else await synthesize(text,voice)
                target.write_bytes(data)
                started = time.perf_counter()
                response = await client.post(f'/api/voice/calls/{call_id}/audio-turn?turn_id=probe',content=data,
                                            headers={'Content-Type':'audio/wav'})
                response.raise_for_status()
                result = response.json()
                entry = {'case':name, 'language':language,'expected_text':text, 'audio':target.relative_to(ROOT).as_posix(),
                    'audio_kind':'synthetic speech, not a human accuracy benchmark', 'result':result,
                    'intended_behavior_reached':bool(result.get('accepted') and result.get('reply',{}).get('grounded')),
                    'request_ms':round((time.perf_counter()-started)*1000)}
                entry['word_errors'] = word_errors(text, result.get('transcript',result.get('review_text','')))
                probes.append(entry)
                print(json.dumps({'probe':name,'accepted':result['accepted'],'transcript':result.get('transcript',result.get('review_text'))}),flush=True)
    accent = {'status':'not_run', 'manual_action':'Run scripts/setup_accent_sample.py before this evaluator.'}
    metadata_file = ROOT / 'data/state/accent/metadata.json'
    if not without_audio and metadata_file.is_file():
        metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
        local_settings = settings.model_copy(update={'whisper_model_dir':settings.localization_whisper_model_dir,
                                                    'asr_timeout_seconds':settings.localization_asr_timeout_seconds})
        audio = prepare_audio((ROOT / metadata['path']).read_bytes())
        started = time.perf_counter()
        result = await WhisperASRProvider(local_settings).transcribe(audio.audio,language='id')
        reference = ' '.join(word for word in metadata['reference_line'].split() if word not in {'|S|','|E|'})
        expected_words = re.findall(r'\w+',reference.casefold())
        actual_words = re.findall(r'\w+',result.text.casefold())
        accent = {**metadata, 'status':'run', 'asr_provider':'faster-whisper 1.2.1', 'model':settings.localization_whisper_model_name + ' multilingual',
            'configured_language':'id', 'reference_text':reference, 'observed_transcript':result.text,
            'decoder_score':result.confidence, 'exact_words_match':expected_words==actual_words,
            'word_errors':word_errors(reference,result.text),
            'fallback_needed':result.confidence<settings.whisper_min_score or not result.text.strip(),
            'terminology_errors':'Not applicable: this news utterance has no required finance terms.',
            'request_ms':round((time.perf_counter()-started)*1000),
            'limitations':'One short clean sample from one speaker; no accent robustness or noisy-finance-call claim. Native-speaker/compliance validation still required.'}
    report = {'calls':calls,'speech_probes':probes,'regional_accent':accent,
        'providers':{'asr':'faster-whisper 1.2.1, ' + settings.localization_whisper_model_name + ' multilingual, CPU int8',
                     'tts':'facebook/mms-tts-tgl and facebook/mms-tts-ind; Windows David for English'},
        'scripted_checks_passed':all(call['passed'] for call in calls)}
    if previous_report:
        report['previous_speech_observations'] = previous_report.get('previous_speech_observations', {
            'providers':previous_report['providers'], 'speech_probes':previous_report['speech_probes'],
            'regional_accent':previous_report['regional_accent']})
    (output / 'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    generate_report(report)
    return 0 if report['scripted_checks_passed'] else 1


def generate_report(report):
    lines = ['# Q3 localization observations', '',
        'Generated from actual HTTP replies and local ASR/TTS calls. Business facts and recorded call dialogue are synthetic. Native-speaker/compliance review remains required.', '',
        '## Executed calls', '', '| Call | Scripted checks | Audio | Transcript / results |', '|---|---|---|---|']
    for call in report['calls']:
        audio = f"[WAV](../{call['audio']})" if call.get('audio') else 'absent'
        lines.append(f"| {call['id']} | {'pass' if call['passed'] else 'fail'} | {audio} | [JSON](../evaluations/localization/{call['id']}.json) |")
    lines += ['', 'These four recordings synthesize scripted customer text and actual agent replies. They cover cooperative payment statements, objections, colloquial/mixed finance wording, same-language fallback, callbacks and escalation. They do not substitute for human call testing.', '',
        '## ASR and TTS', '',
        'ASR configuration: ' + report['providers']['asr'] + '. English uses `en`, Filipino uses `tl`, Taglish uses automatic language detection, and Indonesian uses `id`. Indonesian register is a conversation-state decision, not a separate ASR language. The previous `small.en` adapter remains in use for Q1. Domain vocabulary hints contain terms only, not business rules or expected transcripts.', '',
        'TTS uses local Meta MMS `tgl` for Filipino/Taglish and `ind` for Indonesian. English uses Microsoft David Desktop. MMS is a single-language voice per market; English finance words in mixed speech use that voice, with pronunciation/prosody compromises. Formal/colloquial wording changes, but the voice does not acquire a regional accent. See the pinned revisions in `scripts/setup_localization.py`. MMS model licenses are CC BY-NC 4.0; this setup assumes noncommercial assessment use.', '',
        '| Synthetic speech probe | Expected text | Observed text | Accepted / intended FAQ | WER | Request ms |', '|---|---|---|---|---|---|']
    for probe in report['speech_probes']:
        result = probe['result']
        observed = result.get('transcript',result.get('review_text',''))
        lines.append(f"| {probe['case']} ({probe['language']}) | {probe['expected_text']} | {observed} | {result['accepted']} / {probe['intended_behavior_reached']} | {probe['word_errors']['word_error_rate']} | {probe['request_ms']} |")
    reached = sum(p['intended_behavior_reached'] for p in report['speech_probes'])
    lines += ['', f"Intended speech behavior reached on {reached}/{len(report['speech_probes'])} synthesized probes. This tiny set measures the transport/model/controller behavior, not human accuracy or naturalness. Detailed scores, citations and rejected/reviewed output are retained in [JSON](../evaluations/localization/results.json).", '',
        'Uncertain or unavailable ASR leaves business state unchanged and returns review/type guidance in the current register. Missing evidence and unsupported benefits/fee waivers return a localized human-assistance offer. Missing TTS returns a localized read-the-screen message. Payment statements and spoken callback times require confirmation; no payment, coverage change or fee waiver is executed.', '',
        ]
    previous = report.get('previous_speech_observations')
    if previous:
        previous_passed = sum(p['intended_behavior_reached'] for p in previous['speech_probes'])
        lines += ['## ASR comparison', '',
            f"Previous configuration: {previous['providers']['asr']}. It reached intended behavior on {previous_passed}/{len(previous['speech_probes'])} probes; its exact outputs and durations remain in the JSON under `previous_speech_observations`. The current configuration corrected the Indonesian mixed/colloquial transcriptions in this set but did not resolve the two short Filipino/Taglish probes. The controller also gained recognition of the standard Indonesian question word 'apakah', so intended-behavior changes cannot be attributed solely to the model. The two Filipino/Taglish errors returned localized fallbacks without a business-state update. The synthesized input itself may contribute pronunciation errors; native human testing is needed to separate TTS from ASR error.", '',
            'The colloquial Indonesian baseline also lost a negation. High decoder scores did not guarantee correct words. Payment statements therefore require confirmation regardless of score. Finance-word errors such as premium/pinyo are retained rather than relabeled as successful recognition.', '',
            ]
    lines += ['## Regional-accent observation', '']
    accent = report['regional_accent']
    if accent['status']=='run':
        lines += [f"Tested publisher-labeled **{accent['accent']}** Indonesian human speech from [INDspeech_NEWS_LVCSR]({accent['source']}) at revision `{accent['revision']}`. Source sample: `{accent['publisher_sample']}`; local path: `{accent['path']}`. Duration: {accent['duration_seconds']:.2f} seconds. This is original clean news speech, not a synthesized accent or finance call.", '',
            f"ASR: {accent['asr_provider']}, {accent['model']}, configured language `{accent['configured_language']}`. Reference: `{accent['reference_text']}`. Observed: `{accent['observed_transcript']}`. Exact normalized words match: {accent['exact_words_match']}. Fallback needed under the configured decoder threshold: {accent['fallback_needed']}. Measured request: {accent['request_ms']} ms. Terminology errors: {accent['terminology_errors']}", '',
            'Attribution: ' + accent['citation'] + '. The source is CC BY-NC-SA 4.0 and the publisher prohibits dataset copies in another public repository. Audio is downloaded to ignored `data/state/accent`; only provenance and observations are retained here. Reproduce with `scripts/setup_accent_sample.py`.', '', accent['limitations']]
    else:
        lines += [accent.get('manual_action','Regional-accent test not run.')]
    lines += ['', '## Localization examples', '',
        'The following are implemented draft copy choices, not claims of native-speaker approval.', '',
        '| Market / English intent | Literal phrasing | Implemented phrasing | Reason |', '|---|---|---|---|']
    for example in json.loads((ROOT/'evaluations/localization/examples.json').read_text(encoding='utf-8')):
        lines.append(f"| {example['market']}: {example['intent']} | {example['literal']} | {example['localized']} | {example['explanation']} |")
    lines += ['', '## Manual validation and limits', '',
        '- Have native speakers review Filipino/Taglish and both Indonesian registers, mixed-word pronunciation, politeness and finance language. Obtain approved business sources and regional compliance review before real use.',
        '- Record human conversations per market with explicit consent; the four public WAVs here are synthesized scripted evidence. Expand accent tests to longer finance speech, different regions and noisy microphones.',
        '- Language identification uses explicit selection plus a small deterministic vocabulary. Short acknowledgements preserve register; ambiguous language switches should use the UI selector. This is not broad multilingual intent understanding.',
        '- Callback/escalation only create local mock records. A human must coordinate any actual contact. No payment is verified and no policy is renewed.',
        '- CPU ASR/TTS workers have configured timeouts. These request durations are Q3 observations; Q4 streaming/component measurements are documented separately in the [Q4 report](q4-latency-report.md).', '',
        'Reproduce: install speech dependencies, run `scripts/setup_localization.py`, `scripts/setup_accent_sample.py`, ingest the updated manifest, start the application and run `scripts/evaluate_localization.py`. `--without-audio` records text-only evidence and marks missing speech/accent evidence.']
    (ROOT/'docs/q3-localization-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--without-audio',action='store_true')
    parser.add_argument('--speech-only',action='store_true',help='Reuse executed calls and synthetic WAVs; rerun only speech/accent probes')
    args=parser.parse_args()
    try:
        sys.exit(asyncio.run(evaluate(args.base_url,args.without_audio,args.speech_only)))
    except Exception as exc:
        print(json.dumps({'status':'failed','error_type':type(exc).__name__,
            'manual_action':'Check running services, ingested KB, local speech models and speech timeouts.'}))
        sys.exit(1)
