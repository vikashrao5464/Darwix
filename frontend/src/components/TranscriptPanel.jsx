export default function TranscriptPanel({segments}) {
  return <section aria-label="Live transcript"><h2>Recent transcript</h2>
    {!segments.length&&<p>Waiting for the first audio chunk.</p>}
    {segments.map((s,i)=><article key={s.segment_id??s.chunk_id??i}>
      <strong>{s.speaker}</strong> ({(s.start_ms/1000).toFixed(1)}–{(s.end_ms/1000).toFixed(1)}s)
      <p>{s.text||'[No intelligible speech]'}</p>
      {s.speaker_source&&<small>{s.speaker_source}</small>}
    </article>)}</section>;
}
