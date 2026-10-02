export default function SignalList({signals}) {
  return <section aria-label="Live signals"><h2>Recent signals</h2>
    {!signals.length&&<p>No supported signal yet.</p>}
    {signals.map(s=><article key={s.signal_id}><strong>{s.type.replaceAll('_',' ')}</strong>
      <span> · {s.priority} · {(s.confidence*100).toFixed(0)}%</span><p>{s.evidence}</p></article>)}
  </section>;
}
