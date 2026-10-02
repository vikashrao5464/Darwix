export default function LatencyPanel({samples,summary}) {
  const last=samples.at(-1);
  return <section aria-label="Live latency"><h2>Measured latency</h2>
    <p>Delivery includes dashboard acknowledgement and the return trip. Model warmup is separate.</p>
    {last||summary?.sample_count>0?<table><thead><tr><th>Stage</th><th>{last?'Latest ms':'Restored P50 ms'}</th></tr></thead><tbody>
      {['asr','signal','llm','delivery','end_to_end'].map(key=><tr key={key}>
        <td>{key==='llm'?'Nudge generation':key.replaceAll('_',' ')}</td><td>{(last?last[`${key}_latency_ms`]:summary.metrics[`${key}_latency_ms`].p50_ms).toFixed(1)}</td></tr>)}
      </tbody></table>:<p>Waiting for an acknowledged chunk.</p>}
    {summary?.sample_count>0&&<small>{summary.sample_count} acknowledged samples restored on reconnect.</small>}
  </section>;
}
