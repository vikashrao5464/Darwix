"""Download one regional-accent sample privately, with publisher attribution."""
import hashlib
import io
import json
import re
import sys
import wave
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'ecd9b8bb6d6567d1f486dd60c97497788781034c'
SOURCE = 'https://github.com/s-sakti/data_indsp_news_lvcsr'
BASE = 'https://raw.githubusercontent.com/s-sakti/data_indsp_news_lvcsr/' + REVISION


def main():
    directory = ROOT / 'data/state/accent'
    directory.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        response = client.get(BASE + '/speech/Ind0/Ind001.zip')
        response.raise_for_status()
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        # Publisher labels: B=Batak, J=Javanese, S=Sundanese, U=standard.
        candidates = sorted(name for name in archive.namelist() if re.search(r'_([BJS])_C_news_\d+\.wav$', name))
        if not candidates:
            raise ValueError('no_publisher_labeled_regional_sample')
        selected = None
        for name in candidates:
            audio = archive.read(name)
            with wave.open(io.BytesIO(audio)) as file:
                duration = file.getnframes() / file.getframerate()
            if .5 <= duration <= 18:
                selected = (name, audio, duration)
                break
        if not selected:
            raise ValueError('no_short_accent_sample')
        name, audio, duration = selected
        response = client.get(BASE + '/text/all_transcript.zip')
        response.raise_for_status()
        utterance = re.search(r'news_(\d+)\.wav$', name)[1]
        transcripts = zipfile.ZipFile(io.BytesIO(response.content))
        transcript_name = next((item for item in transcripts.namelist() if re.search(r'news_' + utterance + r'\.', item)), None)
        reference = transcripts.read(transcript_name).decode('utf-8-sig').strip() if transcript_name else None
        if not reference:
            raise ValueError('reference_transcript_not_found')
        target = directory / Path(name).name
        target.write_bytes(audio)
        metadata = {'dataset': 'INDspeech_NEWS_LVCSR', 'source': SOURCE, 'revision': REVISION,
            'license': 'CC BY-NC-SA 4.0; publisher prohibits public dataset copies',
            'citation': 'Sakti et al. (2008), Development of Indonesian Large Vocabulary Continuous Speech Recognition System within A-STAR Project',
            'publisher_sample': name, 'path': str(target.relative_to(ROOT)).replace('\\', '/'),
            'accent': {'B':'Batak', 'J':'Javanese', 'S':'Sundanese'}[re.search(r'_([BJS])_C_', name)[1]],
            'description': 'Original human regional-accent Indonesian clean news speech; not a finance call or synthesized accent.',
            'duration_seconds': duration, 'sha256': hashlib.sha256(audio).hexdigest(),
            'reference_line': reference, 'redistributed_audio': False}
        (directory / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(metadata))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status':'failed', 'error_type':type(exc).__name__,
            'manual_action':'Check source availability; supply a consented regional tester sample if unavailable.'}))
        sys.exit(1)
