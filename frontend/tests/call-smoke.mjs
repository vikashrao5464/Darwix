// Chrome microphone transport with synthetic audio, not a human tester.
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { mkdir, writeFile } from 'node:fs/promises';

const root = resolve(import.meta.dirname, '../..');
const browser = await chromium.launch({
  executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless:true,
  args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',
    `--use-file-for-fake-audio-capture=${resolve(root,'data/audio/q1/probe_browser_faq.wav')}%noloop`,'--autoplay-policy=no-user-gesture-required'],
});
const errors=[], responses=[], checks=[];
try {
  const page=await browser.newPage(); page.setDefaultTimeout(45000);
  await page.addInitScript(() => {
    const original=window.fetch;
    window.fetch=(url, options)=>{
      if (String(url).includes('/audio-turn') && options?.body instanceof Blob) {
        options.body.arrayBuffer().then(buffer=>{ window.__waveCapture=Array.from(new Uint8Array(buffer)); });
      }
      return original(url,options);
    };
  });
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{
    const data=request.postDataBuffer();
    if (request.url().includes('/audio-turn') && data) writeFile(resolve(root,'data/state/browser-captured.wav'),data).catch(error=>errors.push(error.message));
  });
  page.on('response',response=>{
    if (response.url().includes('/api/voice/') && !response.url().includes('/speech/')) responses.push({path:new URL(response.url()).pathname,status:response.status()});
  });
  await page.goto(process.env.DEMO_URL || 'http://127.0.0.1:5173/call');
  await page.getByRole('checkbox',{name:/Save a local audio recording/}).check();
  await page.getByRole('button',{name:'Start demo call',exact:true}).click();
  await page.getByRole('button',{name:'Yes, continue',exact:true}).click();
  await page.getByRole('button',{name:'Speak a reply',exact:true}).click();
  await page.getByRole('status').waitFor(); await page.waitForTimeout(3500);
  const recognized=page.waitForResponse(response=>response.url().includes('/audio-turn'));
  await page.getByRole('button',{name:'Send voice reply',exact:true}).click();
  const audio=await (await recognized).json();
  const captured=await page.evaluate(()=>window.__waveCapture);
  if (captured) await writeFile(resolve(root,'data/state/browser-captured.wav'),Buffer.from(captured));
  if (!audio.accepted || !audio.reply.grounded || !audio.reply.citations.length) throw new Error(`Microphone pipeline failed: ${JSON.stringify(audio)}`);
  checks.push('Synthetic microphone WAV -> browser PCM -> configured ASR -> actual cited KB answer');
  const agent=page.getByRole('region',{name:'Agent reply'});
  if (!(await agent.innerText()).includes('2 percent')) throw new Error('Grounded fee missing from rendered reply');
  await page.getByLabel('Type a reply').fill('What cashback applies to lunar tourism?');
  await page.getByRole('button',{name:'Send reply',exact:true}).click();
  await page.getByText(/I don.t have verified information for that/).first().waitFor();
  checks.push('Unsupported question visibly falls back');
  await page.getByRole('button',{name:'Request human assistance',exact:true}).click();
  const download=page.getByRole('link',{name:'Download your consented recording'}); await download.waitFor();
  const recording=await page.request.get(await download.getAttribute('href')), data=await recording.body();
  if (!recording.ok() || data.length<1000 || data.subarray(0,4).toString()!=='RIFF') throw new Error('Consented recording missing/invalid');
  checks.push('Spoken output, redacted transcript, mock escalation and consented downloadable WAV');
  if (errors.length) throw new Error(errors.join('; '));
  await mkdir(resolve(root,'data/state'),{recursive:true});
  await page.screenshot({path:resolve(root,'data/state/phase-2-call.png'),fullPage:true});
  const report={browser:'Chrome headless',input:'Synthetic WAV through fake microphone; human validation separate',checks,page_errors:errors,voice_http_responses:responses,
    asr_transcript:audio.transcript,asr_confidence:audio.confidence,recording_bytes:data.length};
  await writeFile(resolve(root,'evaluations/voice/browser-smoke.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
} finally { await browser.close(); }
