export default function NudgeCard({nudge}) {
  return <article className={`nudge ${nudge.priority}`} data-testid="nudge">
    <strong>{nudge.priority} priority · {(nudge.confidence*100).toFixed(0)}%</strong>
    <p>{nudge.text}</p><small>Expires at {(nudge.expires_at_ms/1000).toFixed(1)}s of replay time</small>
  </article>;
}
