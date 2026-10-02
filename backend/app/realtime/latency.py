import math

METRICS = ('asr_latency_ms','signal_latency_ms','llm_latency_ms','delivery_latency_ms','end_to_end_latency_ms')
def sample(call_id, chunk_id, received, asr, signal, nudge, delivered):
    return dict(call_id=call_id, chunk_id=chunk_id, audio_received_ms=received, asr_done_ms=asr,
        signal_done_ms=signal, llm_done_ms=nudge, delivered_ms=delivered, asr_latency_ms=asr-received,
        signal_latency_ms=signal-asr, llm_latency_ms=nudge-signal, delivery_latency_ms=delivered-nudge,
        end_to_end_latency_ms=delivered-received)
def percentile(values, quantile):
    values = sorted(values)
    position = (len(values)-1)*quantile
    low, high = math.floor(position), math.ceil(position)
    return round(values[low] + (values[high]-values[low])*(position-low), 3)
def summarize(samples):
    return {'sample_count':len(samples), 'metrics':{key:{'p50_ms':percentile([s[key] for s in samples],.5),
        'p95_ms':percentile([s[key] for s in samples],.95)} for key in METRICS} if samples else {}}
