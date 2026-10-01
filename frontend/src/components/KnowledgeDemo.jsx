import { useEffect, useState } from 'react';
import { api } from '../lib/api';

export default function KnowledgeDemo() {
  const [health, setHealth] = useState('Checking backend…');
  const [query, setQuery] = useState('What documents are required?');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => { api('/health').then(() => setHealth('Backend connected')).catch(() => setHealth('Backend unavailable')); }, []);

  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError(''); setResult(null);
    try {
      const body = { query, product: 'business_loan', language: 'en', top_k: 5 };
      const [answer, search] = await Promise.all([api('/api/knowledge/answer', body), api('/api/knowledge/search', body)]);
      setResult({ answer, search });
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <>
    <h1>Business-loan knowledge demo</h1>
    <p className="notice">Synthetic assessment content. These examples are not Darwix policies.</p>
    <p>{health}. Inspect the same knowledge base used by the call agent.</p>
    <form onSubmit={submit}>
      <label htmlFor="query">Ask about the demo business loan</label>
      <textarea id="query" value={query} maxLength={2000} required onChange={e => setQuery(e.target.value)} />
      <button disabled={busy || !query.trim()}>{busy ? 'Retrieving…' : 'Ask knowledge base'}</button>
    </form>
    <div aria-live="polite">
      {error && <p role="alert">{error}</p>}
      {result && <>
        <h2>{result.answer.grounded ? 'Answer with evidence' : 'Information unavailable'}</h2>
        <p>{result.answer.answer}</p>
        {result.answer.citations.map(c => <p key={c.record_id}>Source: {c.source}, {c.page ? `page ${c.page}, ` : ''}{c.section}, version {c.version} <code>{c.record_id}</code></p>)}
        <details><summary>Inspect retrieval evidence</summary>
          <p>Evidence available: {String(result.search.grounded)}. Search results may include weak matches; only evidence that passes the confidence check can support an answer.</p>
          {result.search.records.map(r => <article key={r.record_id}>
            <h3>{r.title}</h3><p>{r.content}</p>
            <small>Score {r.score.toFixed(4)} · {r.category} · {r.source}{r.source_page ? ` · page ${r.source_page}` : ''} · version {r.version}</small>
          </article>)}
        </details>
      </>}
    </div>
  </>;
}
