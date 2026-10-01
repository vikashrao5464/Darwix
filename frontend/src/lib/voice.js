import { base } from './api';

export function encodeWave(chunks, rate) {
  const size = chunks.reduce((n, chunk) => n + chunk.length, 0);
  const buffer = new ArrayBuffer(44 + size * 2), view = new DataView(buffer);
  const word = (offset, value) => [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  word(0, 'RIFF'); view.setUint32(4, 36 + size * 2, true); word(8, 'WAVE');
  word(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); word(36, 'data'); view.setUint32(40, size * 2, true);
  let offset = 44;
  for (const chunk of chunks) for (const sample of chunk) {
    const value = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, value * (value < 0 ? 32768 : 32767), true); offset += 2;
  }
  return new Blob([buffer], { type: 'audio/wav' });
}

export async function audioRequest(path, blob) {
  const response = await fetch(`${base}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'audio/wav' }, body: blob, signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`Audio request failed (${response.status}). Please type your reply or retry.`);
  return response.json();
}

export class BrowserAudio {
  async open() {
    this.ctx = new AudioContext({ sampleRate: 48000 }); await this.ctx.resume();
    this.mix = this.ctx.createGain(); this.silent = this.ctx.createGain();
    this.silent.gain.value = 0; this.silent.connect(this.ctx.destination);
    // Prototype PCM capture; use AudioWorklet in production.
    this.recorder = this.ctx.createScriptProcessor(4096, 1, 1);
    this.mix.connect(this.recorder); this.recorder.connect(this.silent);
    this.recording = []; this.recordingSamples = 0; this.recordingEnabled = false;
    this.recorder.onaudioprocess = e => {
      if (this.recordingEnabled && this.recordingSamples < this.ctx.sampleRate * 300) {
        const data = e.inputBuffer.getChannelData(0).slice();
        this.recording.push(data); this.recordingSamples += data.length;
      }
    };
  }

  async speak(callId, turnId) {
    const response = await fetch(`${base}/api/voice/calls/${callId}/speech/${turnId}`, { signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error('Spoken output unavailable. Read the agent reply below.');
    const data = await response.arrayBuffer();
    if (!this.ctx || this.ctx.state === 'closed') return;
    const source = this.ctx.createBufferSource(); source.buffer = await this.ctx.decodeAudioData(data);
    source.connect(this.ctx.destination); source.connect(this.mix); this.source = source;
    await new Promise(resolve => { source.onended = resolve; source.start(); });
    if (this.source === source) this.source = null;
  }

  async listen({ deviceId = '', noiseReduction = true, onLevel = () => {}, onDevices = () => {} } = {}) {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access requires localhost or HTTPS.');
    this.stopSpeech();
    // Keep AGC off to avoid clipping. Laptop input can use echo/noise reduction;
    // quiet PCM receives bounded gain before recognition on the backend.
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: {
        ...(deviceId ? {deviceId:{exact:deviceId}} : {}),
        echoCancellation:noiseReduction, noiseSuppression:noiseReduction, autoGainControl:false,
      }, video:false });
      await this.ctx.resume();
      this.mic = this.ctx.createMediaStreamSource(this.stream);
      this.input = this.ctx.createScriptProcessor(4096, 1, 1); this.chunks = []; this.onLevel = onLevel;
      this.input.onaudioprocess = e => {
        const samples=e.inputBuffer.getChannelData(0).slice(); this.chunks.push(samples);
        const rms=Math.sqrt(samples.reduce((sum,value)=>sum+value*value,0)/samples.length);
        onLevel(Math.min(1,rms*12));
      };
      this.mic.connect(this.input); this.input.connect(this.silent); this.mic.connect(this.mix);
      // Enumeration failure must not interrupt a working microphone.
      const devices=await navigator.mediaDevices.enumerateDevices().catch(()=>[]);
      onDevices(devices.filter(device=>device.kind==='audioinput'));
    } catch (error) {
      this.releaseMic(); throw error;
    }
  }

  finishUtterance() {
    if (!this.input) throw new Error('No microphone utterance is active.');
    if (this.chunks.reduce((sum,chunk)=>sum+chunk.length,0) < this.ctx.sampleRate*.1) {
      this.releaseMic();
      throw new Error('No audio was captured yet. Click "Speak a reply", wait for the input meter, then speak and send.');
    }
    const blob = encodeWave(this.chunks, this.ctx.sampleRate);
    this.releaseMic();
    return blob;
  }

  releaseMic() {
    if (this.input) { this.input.onaudioprocess=null; this.input.disconnect(); this.input=null; }
    this.mic?.disconnect(); this.mic=null;
    this.stream?.getTracks().forEach(track=>track.stop()); this.stream=null;
    this.onLevel?.(0);
  }

  stopSpeech() { if (this.source) { this.source.stop(); this.source = null; } }

  async close() {
    this.recordingEnabled = false;
    const blob = this.ctx && this.recording.length ? encodeWave(this.recording, this.ctx.sampleRate) : null;
    this.stopSpeech(); this.releaseMic();
    if (this.recorder) this.recorder.onaudioprocess = null;
    if (this.ctx && this.ctx.state !== 'closed') await this.ctx.close();
    return blob;
  }
}
