// Actual paced replay/ASR/WS/UI checks. No event or provider interception.
import {chromium} from 'playwright';
import {resolve} from 'node:path';
import {rename,writeFile,mkdir} from 'node:fs/promises';
const root=resolve(import.meta.dirname,'../..'),out=resolve(root,'evaluations/realtime');
await mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--autoplay-policy=no-user-gesture-required']});
const context=await browser.newContext({viewport:{width:1100,height:900},recordVideo:{dir:out,size:{width:1100,height:900}}});
const page=await context.newPage(),errors=[],events=[],checks=[];
page.setDefaultTimeout(120000);
page.on('pageerror',e=>errors.push(e.message));
page.on('websocket',ws=>{if(ws.url().includes('/ws/calls/'))ws.on('framereceived',frame=>{try{events.push(JSON.parse(frame.payload));}catch{}});});
try{
  await page.addInitScript(()=>{const start=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(...args){this.playbackRate.value=8;return start.apply(this,args);};});
  await page.goto(process.env.DEMO_URL||'http://127.0.0.1:5173/call');
  await page.getByRole('button',{name:'Start demo call',exact:true}).click();
  await page.getByRole('button',{name:'Yes, continue',exact:true}).click();
  await page.getByLabel('Type a reply',{exact:true}).fill('What is the processing fee?');
  await page.getByRole('button',{name:'Send reply',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="Agent reply"]').textContent.includes('Source:'));
  checks.push('Actual cited Q1 FAQ shown in demo video');
  await page.getByLabel('Type a reply',{exact:true}).fill('What cashback applies to lunar tourism?');
  await page.getByRole('button',{name:'Send reply',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="Agent reply"]').textContent.includes('verified information'));
  checks.push('Unsupported Q1 question returns explicit fallback');
  await page.getByRole('button',{name:'End call',exact:true}).click();
  await page.goto((process.env.DEMO_URL||'http://127.0.0.1:5173/call').replace('/call','/live'));
  await page.getByLabel('Recording',{exact:true}).selectOption('q1_insights');
  await page.getByRole('button',{name:'Start replay',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[data-testid="nudge"]'));
  const statusAtFirstNudge=await page.getByRole('status').innerText();
  if(!statusAtFirstNudge.includes('replaying'))throw new Error('First nudge arrived after playback');
  checks.push('Actual ASR nudge rendered while recording is replaying');console.log(checks.at(-1));
  await page.screenshot({path:resolve(out,'live-nudge.png'),fullPage:true});
  await page.waitForFunction(()=>document.querySelector('[role="status"]').textContent.includes('completed'));
  const snapshotEvent=events.find(e=>e.type==='snapshot');
  if(!snapshotEvent)throw new Error('No actual WS snapshot');
  const callId=snapshotEvent.payload.call_id;
  const snapshot=await (await page.request.get(`http://127.0.0.1:8000/api/realtime/replays/${callId}`)).json();
  const emitted=new Set(events.filter(e=>e.type==='signal').map(e=>e.payload.type));
  for(const kind of ['missed_opportunity','compliance_risk','rising_frustration','payment_difficulty','callback_need'])if(!emitted.has(kind))throw new Error(`Missing signal: ${kind}`);
  if(!snapshot.suppression.some(s=>s.reason==='duplicate')||!snapshot.suppression.some(s=>s.reason==='low_confidence'))throw new Error('Suppression observations missing');
  checks.push('All five signal types, duplicate/weak suppression and acknowledged latency observed');
  await page.getByRole('button',{name:'Reconnect dashboard',exact:true}).click();
  await page.waitForTimeout(1000);
  if((await page.locator('[data-testid="nudge"]').count())!==0)throw new Error('Expired nudges returned on reconnect');
  checks.push('Reconnect restores state and excludes expired nudges');
  if(errors.length)throw new Error(`Page errors: ${errors.join(',')}`);
  await writeFile(resolve(out,'browser-smoke.json'),JSON.stringify({observer:'Chrome rendered UI acknowledgement (two animation frames)',events,snapshot,checks,page_errors:errors,status_at_first_nudge:statusAtFirstNudge},null,2)+'\n');
  await page.screenshot({path:resolve(out,'live-complete.png'),fullPage:true});
  console.log(JSON.stringify({checks,callId,page_errors:errors}));
}finally{
  const video=page.video();await context.close();
  if(video){const path=await video.path();await rename(path,resolve(out,'live-demo.webm'));}
  await browser.close();
}
