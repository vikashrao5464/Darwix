import { useEffect, useRef, useState } from 'react';
import { api, base } from '../lib/api';
import { audioRequest, BrowserAudio } from '../lib/voice';
import KnowledgeDemo from '../components/KnowledgeDemo';

const terminal = new Set(['ended', 'completed', 'escalated', 'declined']);
const label = value => value.replaceAll('_', ' ');
const scenarios = {
  business_loan: {title:'Business-loan qualification', languages:[['en','English']]},
  ph_renewal: {title:'Philippines: life-insurance renewal', languages:[['en','English'],['fil','Filipino / Tagalog'],['fil-en','Taglish']]},
  id_installment: {title:'Indonesia: installment reminder', languages:[['id-formal','Formal Bahasa Indonesia'],['id-colloquial','Colloquial Bahasa Indonesia'],['id-en-mixed','Bahasa with English finance terms']]},
};

export default function CallDemo() {
  const [reply, setReply] = useState(null), [transcript, setTranscript] = useState([]);
  const [text, setText] = useState(''), [busy, setBusy] = useState(false), [listening, setListening] = useState(false);
  const [message, setMessage] = useState(''), [record, setRecord] = useState(false), [download, setDownload] = useState(null);
  const [devices, setDevices] = useState([]), [deviceId, setDeviceId] = useState('');
  const [noiseReduction, setNoiseReduction] = useState(true), [inputLevel, setInputLevel] = useState(0);
  const [reviewText, setReviewText] = useState(null);
  const [scenario, setScenario] = useState('business_loan'), [language, setLanguage] = useState('en');
  const [responseLanguage, setResponseLanguage] = useState('');
  const audio = useRef(null), timer = useRef(null), callId = useRef(null);
  const active = reply && !terminal.has(reply.status);

  useEffect(() => () => {
    clearTimeout(timer.current); audio.current?.close();
  }, []);
  useEffect(() => {
    navigator.mediaDevices?.enumerateDevices().then(list=>setDevices(list.filter(device=>device.kind==='audioinput'))).catch(()=>{});
  }, []);

  async function apply(next) {
    setReply(next);
    if (audio.current) audio.current.recordingEnabled = next.recording_allowed;
    const snapshot = await api(`/api/voice/calls/${next.call_id}`);
    setTranscript(snapshot.transcript);
    try { await audio.current?.speak(next.call_id, next.turn_id); }
    catch (error) { setMessage(error.message); }
    if (terminal.has(next.status)) await finishRecording(next.call_id, next.recording_allowed);
  }

  async function finishRecording(id, save = true) {
    const engine = audio.current; audio.current = null;
    const blob = await engine?.close();
    if (blob && save) {
      const result = await audioRequest(`/api/voice/calls/${id}/recording`, blob);
      setDownload(base + result.download_url);
    }
  }

  async function start() {
    setBusy(true); setMessage(''); setDownload(null); setTranscript([]); setReviewText(null);
    try {
      audio.current = new BrowserAudio(); await audio.current.open();
      const next = await api('/api/voice/calls', { recording_consent: record, scenario, response_language:language });
      setResponseLanguage('');
      callId.current = next.call_id; await apply(next);
    } catch (error) { setMessage(error.message); await audio.current?.close(); audio.current = null; }
    finally { setBusy(false); }
  }

  async function send(value) {
    setBusy(true); setMessage(''); setText(''); setReviewText(null);
    try {
      const next = await api(`/api/voice/calls/${callId.current}/turn`, { turn_id: 'turn_' + crypto.randomUUID(), text: value,
        ...(responseLanguage ? {response_language:responseLanguage} : {}) });
      await apply(next);
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }

  async function stopListening() {
    clearTimeout(timer.current); setListening(false); setBusy(true);
    try {
      const blob = audio.current.finishUtterance();
      const result = await audioRequest(`/api/voice/calls/${callId.current}/audio-turn?turn_id=audio_${crypto.randomUUID()}`, blob);
      if (result.accepted) await apply(result.reply);
      else {
        setMessage(result.message);
        setReviewText(result.review_required ? result.review_text : null);
      }
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }

  async function startListening() {
    setMessage(''); setReviewText(null); setBusy(true);
    try {
      await audio.current.listen({deviceId,noiseReduction,onLevel:setInputLevel,onDevices:setDevices}); setListening(true);
      timer.current = setTimeout(stopListening, 18000);
    } catch (error) { setMessage('Microphone unavailable. Allow microphone access or type your reply.'); }
    finally { setBusy(false); }
  }

  async function end() {
    setBusy(true);
    try {
      const result = await api(`/api/voice/calls/${callId.current}/end`, {});
      setReply(current => ({ ...current, status: result.status })); await finishRecording(callId.current);
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }

  return <>
    <h1>Voice call demo</h1>
    <p className="notice">Synthetic assessment content. This demo cannot approve loans, verify payments, renew policies or contact a real representative.</p>
    <p>Click "Speak a reply", speak one short answer, then click "Send voice reply". Laptop microphones and headsets are supported. Typed replies are available when recognition is unclear.</p>
    {!active && <>
      <label htmlFor="scenario">Call scenario</label>
      <select id="scenario" value={scenario} disabled={busy} onChange={e=>{setScenario(e.target.value);setLanguage(scenarios[e.target.value].languages[0][0]);}}>
        {Object.entries(scenarios).map(([key,value])=><option key={key} value={key}>{value.title}</option>)}
      </select>
      <label htmlFor="language">Starting language / register</label>
      <select id="language" value={language} disabled={busy} onChange={e=>setLanguage(e.target.value)}>
        {scenarios[scenario].languages.map(([key,value])=><option key={key} value={key}>{value}</option>)}
      </select>
      <label className="checkbox"><input type="checkbox" checked={record} onChange={e => setRecord(e.target.checked)} disabled={busy} /> Save a local audio recording after I consent to continue (up to five minutes).</label>
      <p className="muted">Recordings contain your voice and are stored privately on this computer. Use synthetic details. Closing this page discards unsaved audio.</p>
      <button disabled={busy} onClick={start}>{busy ? 'Connecting...' : 'Start demo call'}</button>
    </>}
    {reply && <>
      <p>Status: <strong>{label(reply.status)}</strong> ? Call <code>{reply.call_id}</code></p>
      {reply.language_state && <p>Market: {reply.language_state.market} · Reply language: {reply.language_state.preferred_response_language} · Reminder: {label(reply.reminder_status || 'discussing')}</p>}
      <section aria-label="Agent reply" aria-live="polite"><h2>Agent</h2><p>{reply.text}</p>
        {reply.citations.map(c => <p className="muted" key={c.record_id}>Source: {c.source}{c.page ? `, page ${c.page}` : ''}, {c.section}, version {c.version}</p>)}
      </section>
      {active && <>
        {reply.language_state && <>
          <label htmlFor="response-language">Reply language (applies with your next typed reply)</label>
          <select id="response-language" value={responseLanguage} disabled={busy || listening} onChange={e=>setResponseLanguage(e.target.value)}>
            <option value="">Follow my current language</option>
            {scenarios[reply.scenario].languages.map(([key,value])=><option key={key} value={key}>{value}</option>)}
          </select>
          <p className="muted">For voice, recognition uses the current language. Send a typed reply with your language choice before switching spoken languages.</p>
        </>}
        <div className="microphone">
          <label htmlFor="microphone">Microphone</label>
          <select id="microphone" value={deviceId} onChange={e=>setDeviceId(e.target.value)} disabled={busy || listening}>
            <option value="">System default microphone</option>
            {devices.filter(device=>device.deviceId!=='default').map((device,i)=><option key={device.deviceId} value={device.deviceId}>{device.label || `Microphone ${i+1}`}</option>)}
          </select>
          <label className="checkbox"><input type="checkbox" checked={noiseReduction} onChange={e=>setNoiseReduction(e.target.checked)} disabled={busy || listening} /> Reduce background noise (recommended for laptop microphones)</label>
          <label htmlFor="mic-level">Microphone input level</label>
          <meter id="mic-level" min="0" max="1" value={inputLevel} />
          <p className="muted">{listening ? inputLevel>.01 ? 'Microphone is picking up sound.' : 'Speak now. If the meter stays empty, select another microphone or check its mute/input volume.' : 'The meter activates when you click "Speak a reply".'}</p>
        </div>
        <div className="actions">
          <button disabled={busy && !listening} onClick={listening ? stopListening : startListening}>{listening ? 'Send voice reply' : 'Speak a reply'}</button>
          <button disabled={busy || listening} onClick={end}>End call</button>
        </div>
        {listening && <p role="status">Listening. Click "Send voice reply" when finished (18-second limit).</p>}
        {reviewText !== null && <section aria-label="Review voice transcription">
          <p>Recognition was uncertain. Check and correct what you said before using it.</p>
          <label htmlFor="review-text">Heard text</label>
          <textarea id="review-text" value={reviewText} maxLength={2000} onChange={e=>setReviewText(e.target.value)} disabled={busy || listening} />
          <button disabled={busy || listening || !reviewText.trim()} onClick={()=>send(reviewText)}>Use this reviewed reply</button>
          <button disabled={busy || listening} onClick={()=>setReviewText(null)}>Discard transcription</button>
        </section>}
        <form onSubmit={e => { e.preventDefault(); send(text); }}>
          <label htmlFor="reply">Type a reply</label>
          <textarea id="reply" maxLength={2000} value={text} onChange={e => setText(e.target.value)} disabled={busy || listening} required />
          <button disabled={busy || listening || !text.trim()}>Send reply</button>
        </form>
        {reply.status === 'awaiting_consent' && <div className="actions">
          <button disabled={busy || listening} onClick={() => send(reply.language_state?.market==='ID' ? 'Ya' : reply.language_state?.primary_language==='fil' ? 'Opo' : 'Yes')}>Yes, continue</button>
          <button disabled={busy || listening} onClick={() => send(reply.language_state?.market==='ID' ? 'Tidak' : reply.language_state?.primary_language==='fil' ? 'Hindi po' : 'No')}>No, stop</button>
        </div>}
        <button disabled={busy || listening} onClick={() => send(reply.language_state?.market==='ID' ? 'Saya ingin berbicara dengan petugas' : reply.language_state?.primary_language==='fil' ? 'Gusto ko po ng kinatawan' : 'I want a human representative')}>Request human assistance</button>
      </>}
      {reply.scenario==='business_loan' && <details><summary>Qualification details</summary>
        <table><thead><tr><th>Field</th><th>Value</th><th>Status</th></tr></thead><tbody>
          {Object.entries(reply.qualification.fields).map(([key, field]) => <tr key={key}><td>{label(key)}</td><td>{field.value === null ? '-' : String(field.value)}</td><td>{field.status}</td></tr>)}
        </tbody></table>
        {reply.eligibility && <p>Preliminary result: {label(reply.eligibility.status)}</p>}
        {reply.tools_called.length > 0 && <p>Tools used: {reply.tools_called.join(', ')}</p>}
      </details>}
      <details open><summary>Redacted transcript</summary>
        {transcript.map((segment, i) => <p key={i}><strong>{segment.speaker === 'agent' ? 'Agent' : 'Customer'}:</strong> {segment.text}</p>)}
      </details>
    </>}
    {message && <p role="alert">{message}</p>}
    {download && <p><a href={download} download="demo-call.wav">Download your consented recording</a></p>}
    <details className="knowledge"><summary>Explore the knowledge base separately</summary><KnowledgeDemo /></details>
  </>;
}
