import {useEffect,useRef,useState} from 'react';
import {api,base} from '../lib/api';
import {subscribe} from '../lib/websocket';
import TranscriptPanel from '../components/TranscriptPanel';
import SignalList from '../components/SignalList';
import NudgeCard from '../components/NudgeCard';
import LatencyPanel from '../components/LatencyPanel';

export default function LiveInsights() {
  const [fixtures,setFixtures]=useState([]),[fixture,setFixture]=useState(''),[call,setCall]=useState(null);
  const [segments,setSegments]=useState([]),[signals,setSignals]=useState([]),[nudges,setNudges]=useState([]);
  const [samples,setSamples]=useState([]),[summary,setSummary]=useState(null),[suppressed,setSuppressed]=useState([]);
  const [connection,setConnection]=useState('idle'),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [clock,setClock]=useState(0),[reconnect,setReconnect]=useState(0);
  const clockOrigin=useRef(0),audio=useRef(null);
  useEffect(()=>{api('/api/realtime/fixtures').then(items=>{setFixtures(items);setFixture(items[0]?.fixture_id||'');}).catch(e=>setError(e.message));},[]);
  useEffect(()=>{const timer=setInterval(()=>setClock(performance.now()-clockOrigin.current),250);return()=>clearInterval(timer);},[]);
  useEffect(()=>{
    if(!call?.call_id)return;
    return subscribe(call.call_id,({type,payload:p})=>{
      if(type==='snapshot'){
        setCall(p);setSegments(p.transcripts);setSignals(p.signals);setNudges(p.nudges);setSummary(p.latency);setSuppressed(p.suppression);
        clockOrigin.current=performance.now()-p.elapsed_ms;
      }
      if(type==='status'){
        setCall(p);clockOrigin.current=performance.now()-p.elapsed_ms;
        if(p.status==='replaying'&&audio.current){audio.current.currentTime=0;audio.current.play().catch(()=>setError('Use the recording Play control to hear audio. Analysis continues.'));}
        if(['stopped','failed','completed'].includes(p.status))audio.current?.pause();
      }
      if(type==='transcript'){
        setSegments(old=>[...old,p].filter(s=>s.end_ms>=p.end_ms-45000).slice(-40));
        if(p.usable)setError('');
      }
      if(type==='signal')setSignals(old=>[...old,p].slice(-40));
      if(type==='nudge')setNudges(old=>[...old,p].slice(-40));
      if(type==='latency')setSamples(old=>[...old,p].slice(-100));
      if(type==='suppressed')setSuppressed(old=>[...old,p].slice(-40));
      if(type==='warning')setError(p.reason);
    },setConnection);
  },[call?.call_id,reconnect]);
  const active=call&&['preparing','replaying','draining'].includes(call.status);
  const playback=call?.status==='replaying'?clock:(call?.playback_finished_ms||0);
  async function start(){
    setBusy(true);setError('');setSegments([]);setSignals([]);setNudges([]);setSamples([]);setSuppressed([]);
    try{setCall(await api('/api/realtime/replays',{fixture_id:fixture}));}catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function stop(){try{setCall(await api(`/api/realtime/replays/${call.call_id}/stop`,{}));}catch(e){setError(e.message);}}
  const liveNudges=nudges.filter(n=>n.expires_at_ms>clock).sort((a,b)=>(a.priority==='high'?-1:1)-(b.priority==='high'?-1:1));
  return <><h1>Live call insights</h1>
    <p className="notice">Synthetic demo recordings. Nudges guide an agent and perform no business action. Speaker labels use recording annotations; diarization is unavailable.</p>
    <label htmlFor="replay-fixture">Recording</label><select id="replay-fixture" value={fixture} onChange={e=>setFixture(e.target.value)} disabled={active}>
      {fixtures.map(f=><option key={f.fixture_id} value={f.fixture_id}>{f.title} ({(f.duration_ms/1000).toFixed(0)}s)</option>)}
    </select>
    <div className="actions"><button onClick={start} disabled={active||busy||!fixture}>Start replay</button>
      <button onClick={stop} disabled={!active}>Stop replay</button>
      <button onClick={()=>setReconnect(n=>n+1)} disabled={!call}>Reconnect dashboard</button></div>
    {fixture&&<audio ref={audio} controls src={`${base}/api/realtime/fixtures/${fixture}/audio`} preload="metadata" aria-label="Replay recording"/>}
    <p role="status">Call: {call?.status||'idle'} · {connection}{call&&` · ${call.call_id}`}</p>
    {call&&<p>Playback: {Math.floor(Math.min(playback,call.duration_ms)/1000)} / {Math.ceil(call.duration_ms/1000)}s · {Math.max(samples.length,call.counts?.chunks||0)} analyzed chunks</p>}
    {(error||call?.error)&&<p role="alert">{call?.error||error}</p>}
    <section aria-label="Active nudges"><h2>Active nudges</h2>{liveNudges.length?liveNudges.map(n=><NudgeCard key={n.nudge_id} nudge={n}/>):<p>No active nudge.</p>}</section>
    <TranscriptPanel segments={segments}/><SignalList signals={signals.filter(s=>s.detected_at_ms>clock-45000)}/>
    <LatencyPanel samples={samples} summary={summary}/>
    <details><summary>Suppression observations ({suppressed.length})</summary>{suppressed.map((s,i)=><p key={i}>{s.type}: {s.reason} (chunk {s.chunk_id})</p>)}</details>
  </>;
}
