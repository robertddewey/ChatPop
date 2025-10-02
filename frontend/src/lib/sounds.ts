/**
 * Sound utility functions using Web Audio API
 * Singleton pattern to maintain unlocked AudioContext for iOS Safari
 */

// Singleton AudioContext that persists across the app
let globalAudioContext: AudioContext | null = null;

// Initialize and unlock the AudioContext (call this from a user gesture)
export const initAudioContext = async (): Promise<AudioContext | null> => {
  try {
    if (!globalAudioContext) {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextClass) {
        console.log('AudioContext not supported');
        return null;
      }
      globalAudioContext = new AudioContextClass();
      console.log('AudioContext created');
    }

    // Always resume on iOS (required after page load or context suspension)
    if (globalAudioContext.state === 'suspended') {
      await globalAudioContext.resume();
      console.log('AudioContext resumed');
    }

    console.log('AudioContext state:', globalAudioContext.state);
    return globalAudioContext;
  } catch (error) {
    console.log('Failed to init AudioContext:', error);
    return null;
  }
};

// Get the global audio context (returns null if not initialized)
export const getAudioContext = (): AudioContext | null => {
  return globalAudioContext;
};

// Generate a clean, pleasant success chime as base64 WAV
// This creates a C major chord arpeggio (C-E-G) that sounds pleasant
const generateSuccessChime = (): string => {
  const sampleRate = 44100;
  const duration = 0.4; // 400ms
  const numSamples = Math.floor(sampleRate * duration);

  // Create WAV header
  const createWavHeader = (dataSize: number): ArrayBuffer => {
    const buffer = new ArrayBuffer(44);
    const view = new DataView(buffer);

    // "RIFF" chunk descriptor
    view.setUint32(0, 0x52494646, false); // "RIFF"
    view.setUint32(4, 36 + dataSize, true); // File size - 8
    view.setUint32(8, 0x57415645, false); // "WAVE"

    // "fmt " sub-chunk
    view.setUint32(12, 0x666d7420, false); // "fmt "
    view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
    view.setUint16(20, 1, true); // AudioFormat (1 = PCM)
    view.setUint16(22, 1, true); // NumChannels (1 = mono)
    view.setUint32(24, sampleRate, true); // SampleRate
    view.setUint32(28, sampleRate * 2, true); // ByteRate
    view.setUint16(32, 2, true); // BlockAlign
    view.setUint16(34, 16, true); // BitsPerSample

    // "data" sub-chunk
    view.setUint32(36, 0x64617461, false); // "data"
    view.setUint32(40, dataSize, true); // Subchunk2Size

    return buffer;
  };

  // Generate audio samples (C major arpeggio)
  const samples = new Int16Array(numSamples);
  const notes = [523.25, 659.25, 783.99]; // C5, E5, G5
  const noteDuration = duration / 4;

  for (let i = 0; i < numSamples; i++) {
    const t = i / sampleRate;
    let sample = 0;

    // Play notes sequentially
    notes.forEach((freq, noteIndex) => {
      const noteStart = noteIndex * noteDuration;
      const noteEnd = noteStart + noteDuration;

      if (t >= noteStart && t < noteEnd) {
        const noteT = t - noteStart;
        const envelope = Math.sin(Math.PI * noteT / noteDuration);
        sample += envelope * Math.sin(2 * Math.PI * freq * noteT) * 0.3;
      }
    });

    samples[i] = Math.max(-32768, Math.min(32767, sample * 32767));
  }

  // Combine header and data
  const header = createWavHeader(samples.byteLength);
  const wavData = new Uint8Array(header.byteLength + samples.byteLength);
  wavData.set(new Uint8Array(header), 0);
  wavData.set(new Uint8Array(samples.buffer), header.byteLength);

  // Convert to base64
  let binary = '';
  for (let i = 0; i < wavData.byteLength; i++) {
    binary += String.fromCharCode(wavData[i]);
  }
  return 'data:audio/wav;base64,' + btoa(binary);
};

// Play a pleasant "success" sound when joining chat
export const playJoinSound = async () => {
  try {
    // Try HTML5 Audio first (more reliable on iOS Safari)
    const audio = new Audio();

    // Generate a pleasant chime
    audio.src = generateSuccessChime();

    audio.volume = 0.6;

    const playPromise = audio.play();

    if (playPromise !== undefined) {
      await playPromise;
      console.log('Join sound played successfully (HTML5 Audio)');
    }
  } catch (htmlError) {
    console.log('HTML5 Audio failed, trying Web Audio API:', htmlError);

    // Fallback to Web Audio API
    try {
      const audioContext = await initAudioContext();
      if (!audioContext || audioContext.state !== 'running') {
        console.log('AudioContext not available or not running');
        return;
      }

      // Create a short buffer with a pleasant sound
      const sampleRate = audioContext.sampleRate;
      const duration = 0.15; // Shorter duration
      const buffer = audioContext.createBuffer(1, sampleRate * duration, sampleRate);
      const data = buffer.getChannelData(0);

      // Generate a single beep
      const frequency = 880; // A5 note

      for (let i = 0; i < data.length; i++) {
        const t = i / sampleRate;
        const envelope = Math.sin(Math.PI * t / duration); // Smooth envelope
        data[i] = envelope * Math.sin(2 * Math.PI * frequency * t) * 0.5;
      }

      // Play the buffer
      const source = audioContext.createBufferSource();
      source.buffer = buffer;
      source.connect(audioContext.destination);
      source.start(0);

      console.log('Join sound played successfully (Web Audio API)');
    } catch (error) {
      console.log('All audio playback methods failed:', error);
    }
  }
};

// Future: Play sound for message pin
export const playPinSound = async () => {
  // TODO: Implement pin sound (higher pitched notification)
};

// Future: Play sound for tip received
export const playTipSound = async () => {
  // TODO: Implement tip sound (pleasant chime)
};
