"""Download the public English ASR model once; microphone audio stays local."""
import json
import os
import sys
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "2"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    from app.config import Settings
    from faster_whisper.utils import download_model
    settings = Settings()
    path = settings.whisper_model_dir
    if not path.is_absolute():
        path = ROOT / path
    try:
        revisions={"base.en":"3d3d5dee26484f91867d81cb899cfcf72b96be6c",
                   "small.en":"d1d751a5f8271d482d14ca55d9e2deeebbae577f"}
        download_model(settings.whisper_model_name, output_dir=str(path), use_auth_token=False,
                       revision=revisions[settings.whisper_model_name])
        print(json.dumps({"model_ready":True,"model":settings.whisper_model_name,"directory":str(path)}))
        return 0
    except Exception as exc:
        print(json.dumps({"model_ready":False,"error_type":type(exc).__name__,
            "manual_action":"Check internet access/model availability, then rerun scripts/setup_asr.py."}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
