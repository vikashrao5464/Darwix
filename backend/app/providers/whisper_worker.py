"""One local recognition job. Audio/model contents never go to logs or a service."""
import argparse
import json
import math
import os
from pathlib import Path

# Bound native thread pools before importing the model runtime.
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "2"


def transcribe(model, audio):
    segments, _ = model.transcribe(audio, language="en", beam_size=5, temperature=0,
        condition_on_previous_text=False, vad_filter=True,
        vad_parameters={"min_silence_duration_ms":300}, no_speech_threshold=.6)
    text, scores = [], []
    for segment in segments:
        if not segment.text.strip():
            continue
        # This is a decoder evidence score, not calibrated recognition accuracy.
        if segment.no_speech_prob > .6 or segment.compression_ratio > 2.4:
            continue
        score = min(1.0, math.exp(segment.avg_logprob))
        text.append(segment.text.strip())
        scores.append(score)
    return {"text":" ".join(text), "confidence":min(scores) if scores else 0.0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=args.threads,
        num_workers=1, local_files_only=True)
    result = transcribe(model, args.input)
    Path(args.output).write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()
