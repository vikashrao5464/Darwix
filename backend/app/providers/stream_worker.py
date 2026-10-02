"""Private PCM chunks in, final ASR JSON out. No reference transcripts or role labels."""
import argparse
import base64
import io
import json
import sys
import wave
import numpy as np
from faster_whisper import WhisperModel

def run():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',required=True); parser.add_argument('--language',required=True)
    parser.add_argument('--threads',type=int,default=2)
    args=parser.parse_args()
    model=WhisperModel(args.model,device='cpu',compute_type='int8',cpu_threads=args.threads,local_files_only=True)
    print(json.dumps({'ready':True}),flush=True)
    for line in sys.stdin:
        audio=base64.b64decode(json.loads(line)['audio'],validate=True)
        with wave.open(io.BytesIO(audio),'rb') as source:
            samples=np.frombuffer(source.readframes(source.getnframes()),dtype='<i2').astype(np.float32)/32768
            rate=source.getframerate()
        if rate != 16000:
            positions=np.arange(round(len(samples)*16000/rate))*rate/16000
            samples=np.interp(positions,np.arange(len(samples)),samples).astype(np.float32)
        if not len(samples) or np.sqrt(np.mean(samples*samples)) < .004:
            print(json.dumps({'text':'','confidence':0}),flush=True); continue
        segments,_=model.transcribe(samples,language=args.language,beam_size=5,vad_filter=True,
            condition_on_previous_text=False,temperature=0)
        segments=list(segments)
        # Match the existing utterance worker's decoder-score definition.
        import math
        useful=[s for s in segments if s.no_speech_prob < .65]
        text=' '.join(s.text.strip() for s in useful)
        score=sum(math.exp(s.avg_logprob)*(1-s.no_speech_prob) for s in useful)/len(useful) if useful else 0
        print(json.dumps({'text':text,'confidence':max(0,min(1,score))}),flush=True)

if __name__=='__main__': run()
