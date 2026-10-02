"""Local MMS synthesis; model/text are supplied as private file paths."""
import argparse
import os
import wave
from pathlib import Path

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['OMP_NUM_THREADS'] = '2'


def main():
    parser = argparse.ArgumentParser()
    for name in ('model', 'input', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    import numpy as np
    import torch
    from transformers import VitsModel, VitsTokenizer
    torch.set_num_threads(2)
    torch.manual_seed(555)
    model = VitsModel.from_pretrained(args.model, local_files_only=True).eval()
    tokenizer = VitsTokenizer.from_pretrained(args.model, local_files_only=True)
    text = Path(args.input).read_text(encoding='utf-8')
    inputs = tokenizer(text, return_tensors='pt')
    with torch.inference_mode():
        audio = model(**inputs).waveform[0].numpy()
    pcm = np.rint(np.clip(audio, -1, 1) * 32767).astype('<i2')
    with wave.open(args.output, 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(model.config.sampling_rate)
        output.writeframes(pcm.tobytes())


if __name__ == '__main__':
    main()
