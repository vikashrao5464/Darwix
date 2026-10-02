"""Prepare pinned public speech models. All call inference uses local files."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
MODEL_REVISIONS = {'small':'2ec96c5472da50d38d40c0cfe0602af2e94b4c8a',
                   'medium':'08e178d48790749d25932bbc082711ddcfdfbc4f'}
TTS_REVISIONS = {'tgl': '79182edde3d60484a9e7a666240917f454138a0b',
                 'ind': '50dc8c10320a328391efaab25e4c629f9bf254ec'}


def main():
    from app.config import Settings
    from faster_whisper.utils import download_model
    from huggingface_hub import snapshot_download
    settings = Settings()
    revision = MODEL_REVISIONS[settings.localization_whisper_model_name]
    download_model(settings.localization_whisper_model_name, output_dir=str(settings.localization_whisper_model_dir),
                   revision=revision, use_auth_token=False)
    print(json.dumps({'ready': 'multilingual ASR', 'model':settings.localization_whisper_model_name, 'revision': revision}), flush=True)
    for language, revision in TTS_REVISIONS.items():
        snapshot_download('facebook/mms-tts-' + language, revision=revision, token=False,
                          local_dir=str(settings.localization_tts_model_dir / language),
                          allow_patterns=['*.json', '*.bin', '*.safetensors', 'README.md'])
        print(json.dumps({'ready': 'MMS TTS ' + language, 'revision': revision}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'ready': False, 'error_type': type(exc).__name__,
            'manual_action': 'Check internet access, then rerun scripts/setup_localization.py.'}))
        sys.exit(1)
