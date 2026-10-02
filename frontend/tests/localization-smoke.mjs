// Actual Q3 API/model transport; synthetic microphone and accelerated playback.
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { writeFile } from 'node:fs/promises';

const root=resolve(import.meta.dirname,'../..');
const browser=await chromium.launch({
  executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless:true,
  args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',
    `--use-file-for-fake-audio-capture=${resolve(root,'data/audio/q3/probe_id_formal.wav')}%noloop`,
    '--autoplay-policy=no-user-gesture-required'],
});
const errors=[],checks=[],speech=[];
try {
  const page=await browser.newPage();
  page.setDefaultTimeout(90000);
  await page.addInitScript(()=>{
    const original=AudioBufferSourceNode.prototype.start;
    AudioBufferSourceNode.prototype.start=function(...args){this.playbackRate.value=8;return original.apply(this,args);};
  });
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{
    if(response.url().includes('/speech/'))speech.push({path:new URL(response.url()).pathname,status:response.status()});
  });
  await page.goto(process.env.DEMO_URL || 'http://127.0.0.1:5173/call');
  await page.getByLabel('Call scenario',{exact:true}).selectOption('id_installment');
  await page.getByLabel('Starting language / register',{exact:true}).selectOption('id-formal');
  await page.getByRole('button',{name:'Start demo call',exact:true}).click();
  await page.getByRole('button',{name:'Yes, continue',exact:true}).click();
  const agent=page.getByRole('region',{name:'Agent reply'});
  await page.waitForFunction(()=>document.querySelector('[aria-label="Agent reply"]').textContent.includes('tujuh ratus'));
  checks.push('Formal Indonesian consent -> actual localized cited reminder');
  console.log(checks.at(-1));
  await page.getByRole('button',{name:'Speak a reply',exact:true}).click();
  await page.getByRole('status').waitFor();
  await page.waitForTimeout(3500);
  const recognition=page.waitForResponse(response=>response.url().includes('/audio-turn'));
  await page.getByRole('button',{name:'Send voice reply',exact:true}).click();
  const audio=await (await recognition).json();
  if(!audio.accepted || !audio.reply.grounded)throw new Error(`Q3 microphone failed: ${JSON.stringify(audio)}`);
  checks.push('Synthetic Indonesian microphone -> multilingual Whisper -> cited tenor explanation');
  console.log(checks.at(-1));
  await page.getByLabel('Type a reply',{exact:true}).fill('xyz zzz');
  await page.getByRole('button',{name:'Send reply',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="Agent reply"]').textContent.includes('terverifikasi'));
  checks.push('Indonesian unknown reply keeps formal fallback');
  await page.getByRole('button',{name:'Request human assistance',exact:true}).click();
  await page.getByRole('button',{name:'Start demo call',exact:true}).waitFor();
  await page.getByLabel('Call scenario',{exact:true}).selectOption('ph_renewal');
  await page.getByLabel('Starting language / register',{exact:true}).selectOption('fil-en');
  await page.getByRole('button',{name:'Start demo call',exact:true}).click();
  await page.getByRole('button',{name:'Yes, continue',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="Agent reply"]').textContent.includes('one thousand'));
  await page.getByLabel('Type a reply',{exact:true}).fill('Ano po ang premium?');
  await page.getByRole('button',{name:'Send reply',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="Agent reply"]').textContent.includes('Ang premium po'));
  if(!(await agent.innerText()).includes('Source: data/raw/ph_reminder_taglish.json'))throw new Error('Taglish citation missing');
  checks.push('Taglish selection -> real cited FAQ and localized speech output');
  console.log(checks.at(-1));
  await page.getByLabel('Type a reply',{exact:true}).fill('xyz zzz');
  await page.getByRole('button',{name:'Send reply',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="Agent reply"]').textContent.includes('verified info'));
  checks.push('Unknown Taglish input preserves fallback register');
  await page.getByRole('button',{name:'End call',exact:true}).click();
  await page.getByRole('button',{name:'Start demo call',exact:true}).waitFor();
  if(errors.length || speech.some(item=>item.status!==200))throw new Error(JSON.stringify({errors,speech}));
  const report={browser:'Chrome headless',input:'Synthetic fake microphone; native speech playback accelerated 8x for UI checks',
    checks,page_errors:errors,speech_responses:speech,asr_transcript:audio.transcript,asr_confidence:audio.confidence};
  await writeFile(resolve(root,'evaluations/localization/browser-smoke.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
} finally {await browser.close();}
