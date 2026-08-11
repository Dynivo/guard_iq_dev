/** Convert browser MediaRecorder blobs (webm/ogg/mp4) to 16 kHz mono PCM WAV for Azure STT. */

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
}

function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, 'WAVE');
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, 'data');
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }
  return new Blob([buffer], { type: 'audio/wav' });
}

function mixToMono(buffer: AudioBuffer): Float32Array {
  const { numberOfChannels, length } = buffer;
  if (numberOfChannels === 1) return buffer.getChannelData(0);
  const out = new Float32Array(length);
  for (let ch = 0; ch < numberOfChannels; ch++) {
    const data = buffer.getChannelData(ch);
    for (let i = 0; i < length; i++) out[i] += data[i] / numberOfChannels;
  }
  return out;
}

/**
 * Decode any browser-recorded audio blob and re-encode as 16 kHz mono WAV
 * (format Azure Speech REST handles reliably).
 */
export async function audioBlobToWav16k(blob: Blob): Promise<Blob> {
  if (!blob.size) throw new Error('Empty recording');

  const AudioCtx =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new AudioCtx();
  try {
    const ab = await blob.arrayBuffer();
    const decoded = await ctx.decodeAudioData(ab.slice(0));
    const mono = mixToMono(decoded);
    const targetRate = 16000;
    const duration = decoded.duration;
    const frameCount = Math.max(1, Math.ceil(duration * targetRate));
    const offline = new OfflineAudioContext(1, frameCount, targetRate);
    const offlineBuffer = offline.createBuffer(1, mono.length, decoded.sampleRate);
    const channel = offlineBuffer.getChannelData(0);
    channel.set(mono);
    const source = offline.createBufferSource();
    source.buffer = offlineBuffer;
    source.connect(offline.destination);
    source.start(0);
    const rendered = await offline.startRendering();
    return encodeWav(rendered.getChannelData(0), targetRate);
  } finally {
    await ctx.close().catch(() => undefined);
  }
}
