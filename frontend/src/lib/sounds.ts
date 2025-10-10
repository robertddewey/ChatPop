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
    }

    // Always resume on iOS (required after page load or context suspension)
    if (globalAudioContext.state === 'suspended') {
      await globalAudioContext.resume();
    }
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

// Generate long press sound from jsfxr (pre-encoded WAV)
const generateLongPressSound = (): string => {
  // WAV file from jsfxr - exact sound from the editor
  return 'data:audio/wav;base64,UklGRmgVAABXQVZFZm10IBAAAAABAAEARKwAAESsAAABAAgAZGF0YUQVAAB/gIB/f3+AgH+AgH+Af4B/gIB/f39/gH+AgH9/f4B/gICAgH9/f3+AgH+AgH9/gH+Af39/gH+AgIB/gH+AgH+Af4CAgH9/gICAf3+AgIB/gICAf3+Af3+AgIB/f39/f3+Af4CAf3+Af3+Af39/f4CAf4CAf39/gIB/f4CAf4CAgH+Af4B/gICAf39/gIB/gH+Af4B/f4CAgIB/f3+Af4CAf4CAgH+AgH9/f39/gICAf3+AgICAf3+AgH+Af39/f4B/f4CAgIB/gIB/f4B/gICAf4CAf4CAf4B/f4CAf4B/f4CAgH9/f4B/f3+AgH9/f39/gH+AgH+AgH+Af3+AgH+Af39/f4B/gH+Af3+AgH+AgICAgH+AgH9/gH+Af39/f4CAf39/gH+AgH+BfoB/f4CAgIB/f4CAf3+Af4B/gH+Af39/f39/gIB/gX+AgIB/gICAgH+Af3+Af4CAf4B+f4CAgICAf3+Af39/gICAf4B/gIB/gIB+gIB/gH+AgH5/gICAf35/gIGAgIB/f39/f39/f4CAgH5/f4B/gICBgYB/fn+Af3+AgH+BgX9/f3+AgH+Af39/gICAf4B+f4B/gX9/f4B/f3+Af4B/f4CAgH9+f4CAfoCBgH+Af36Af39/f4CAgH9/gIB/f39/gX+Af4GAf31/gIF/gIB/foF/gH9/gIB+foB/gH9/gIB+gX+BgX9/fn+Af39/gX+AgX9+gX6AgICAgICAf4CAf39/gICAfn9/gH9/gH9+gYF/foF/f35/gX9/f4CAgX+AgH6Af39/gX9+gn9/gIB+gICAgYB/f35+gH+Af3+BgICAf39/f3+Af39/gIGBfn5/f3+CgICBf4CAf3+Af39+gH9/gX9/gX+Bf4B/gIF/gX9/foB/gH5/gH+AgYB/foCAfn+Afn6AgIGBf4CAf31/gIKAf3+Af4F+gH9/f4GBgIB/f4CAgYCAfX9/f3+AgYB/f39+gYCAfoF/fn+CgIB/f36BgIF/fYCAf36Af4B+gIB/f4J+foCAgIF/gn5+gIB/gIF+f39/gICAgH+AfoCAgH5/gIB9gICCgn9/gIF/f36BgIB/gX9+gICBgH9/fH6CgH9/gn99f4N/foCBgYCAgH1/fn+AgX6CfoB+gX+Bf35/f36AfYF/gICCf36Cf4B/gIGAfX5/gX9/foB/f4J+gH6BgIGBfYB9f4F/f4F/gYF8gX+Bf36AfoGAf3+BfH+Cfn6CgH59gYB/gX6AgH6AgoF/fX6AgIB+f4B/foCDfoCAgoB/gH9+f4F/fn+AgX99f4KBf4CBfX6Agnx9f4N/foGCgIB/fIF/f4GAfX+AfYF/f4B9gICAf3+Cgnx+f3+AgYF9gH+Af36Af36BgH+Cf3+BfoCBfn2Agn59gYF+foF/gIGBfoB/f3+AgX1/foOAf4F+gYF/f3x+gIGAf4CCfYB+f36AgYGBf39+gX2AgH6Bf3+CgICBf32Cf399gX1+hH1+gH+Bg31/foF/fn6CgoCAf31+gn+BfX9/gX9+f4N/f4F9gH2CgX+AgH6Af4F/fYCCgoJ8gHx9goB/foCAf4B/gX6BgYB+f4GCf359hH2BfH5+g36BgH+AgIJ+e4CAfn+BfX9/gIGEgoB8f36CgX5/gYCAfX+Cf4J8foCBfn6DfYKAf35+gYF8gH+BgH6AfoF+f4GBf3+BfIOBgH5/gIB+fIB9goJ/fH+Bf4R8g4GBe39/fIF+gIKCgX1/gH2AgX+Cgnx9f39/gYF9goB8fn+Cg4CCf398gH1+gX6EgX+AgX2Bfn99foN/fYGAf39+gX2De4F9gX6Bgn+Bf3uCf36Bf32CgX+BgX6BfIB+fn9/fYN/foJ/gH+BfICBfn6DfoJ/fn+Afn+BgoCAfn6BfYODf3qAfYCDf35+gICBfoGCf31/gIF/gYF9e4CEfYOAfISAgXx7fYGAgH9+f4KCgX59gn6CfoN9gH9+gn5+gX+BgXx+f4J+fIN/gYB9fYOBfoCAgH99goGAgH19foaAgX18fYCAfYSAf4CBfYF/gYGCen2DfIJ8g36Af36ChH1/f4CDfXuAgoJ/fX9+gn99g3yAfoSEe36CgXx/hIJ7foF6fX6Ff4KCe4F9goR9gIB8f36CgoGAfYB9goB+f399gYKCfnx9g4B9hYJ9fX2BfYKAfoF+gn9/gIODeX1+hH5/hYCAfXyCf36AgXx+g3uEf4N8foB/gn6Ae4GBg399gX+FfX6AgoB/gn99f35/foR9f4KCeYCBf4KCgIJ5gH58goN5g4N/e36Bf4F9gX5/f4WDfX9+gH5+f4R+fYF8hIKAe4R7f32Dgnt9gn5+hYR9eoKCfYB8fH6AhYB+hYKAgIF9fH18hYJ/e4J/gIF+fn2AfoKCgXqBgX19gn+DfH2AgoR/gHmEf4J+en+AhH5+hIF/fXuAgoF+e4OAgXyCgH+AgHqBgX58goR6gIN6g39+fn6BgoB+f4N+gYN5gIR9hH95g39+foJ7gn+Cg32Bgn+Aen6Agn99hIJ8gH1/hIGAgX6BfIB9gIF9gn58gX2Ef4OCe4F4hoCDfnqFfn9/gX1+f4V5f4KBg3uBgH9/fH+CgICBf4GBf3qBfoB9goB/gH+EfH9/hYF+fH99e4KCgXyChIJ5f4J+foV7g4J+eICEfIF8gId+e3yGgH9+gYB9fIaCgYB9fICAfXx9hIGFgYJ6f4B8gH+EgoB+gYB+fIR+fHqGf3+Eg3t8e4ODgYB+eYV6gX+DgH99gYWAeH2Dg4B9fX+FfoB8g3t+gYB/foOAeYd+gH6EeoJ8fYV9hH2BfoR8fn2GgYB6fYB/gn2CgICAfYGAfYF7gn9+gn6BgHyBfoN+fIOCfH+DhYB7gX97hn+AfX2BfoR+hH1/f3t8gIKDgYOAe4GAeYGFf4OAfn+Ae31+hoJ7fICCe4J/f4V/eoGAfIF9hn+FfH97foKBg4N7fn57gnuBgXyBgn+DeXyDgYN+fIOAgnqBfICBgYCAgX98fnyFfYKCfYJ8goR7goF9foV8g4B9gn57foN5f4d/gHyDgHx+g4F8g32FfHuAfIB/fH+DfYF8g4h6gnyCgoGDfn9+gYF7fIV/fnyCgYN/f4J/en9/g3yFfIB+f4KDgnmAfYCCgn18f319iH2AfYN7gYJ8gYF7fYR/e4CIhHp+g36DgXh7goJ7gId4gXx/fYeBeoJ7hXyAfYJ/hIWAfX58g4OAeX19gYJ8g36Agnt9f36Ffn5+h4B9f4KFfX+CfH2Cf3mAf3+Cg357fYeDgnl+hHiHgHx+hXh/gn2CfX97gYCEgYOAfn1+f35+gYOBgnp+fIaAfYV7gYZ+e3qDhX6AfIF9gn5+gHyEe4OFfYF5gIaCfoWBe32DeH9+g3yAhH97f4d3g3+EfH6BfX+FfXiFgIN9g3x+g4N9fnuBhYaBfHyHd4GBhHqAgIR+d4GBfnt/fIaEfX5/gXx9f3+DhnqDhXh+f3+AhHl5hIV7fIR5hoB8h36BhHl9gIOCfnqEfX+CgYJ7foWEd3yFf32Df3t8fX6Fgn+CgXuBgH2Be3+Hgn18hIB9fIJ8gIV5gH+AhIN6fIF7gIGLenyIf398gXmEgIWAenyDg3iCfXl/hYKAhYB5gn59f4R9foaCfX58f4GBfn54goCCf3mBhX6Fen+Eg314f4KCgoKEeXqHfoCBdoODfXqCfn+IeIF8foGEfn97goqBfHx6g4J9e4WEfX5/iYF/gXd7e4d6fIWBhHuBfnx+iYOAfYB/hHmBfICHg3p/fHyEgX6EgX56fYSCf3t9enyCgIt/fYF+goN9hnmAfYF8fH+Gf3yDfYZ9gHqAeYCDg3yIfIJ3hX2GeoiBeYSAe397gYN6foGDeX+BfH2Kfn6FhIOBd3+AhHd8f4GIhYB8fX9+e4CGfnmChoKDgHh+en6BgIiDeX6Af4B9fISAgHeOeICEd36IfH+DfoF9eoSDhIR9fHyCgn9/gYF8fXyHgXmGfX17e4x4gH+Fgn56fnt/god6hIKBfYR5gn2GgHx/eH+IeXyJgHt/eoiDfHt5hod5hX5+eoJ5ioV8iYJ5fYB/gX6Cd359goV5eot8f35/gXuCf4CDhHN9f4GBhnyIg3V+iHt7hYGAeIZ5gn+AgYF/iHl7gHuAgYKAgH2Lf3t/e4N5goGGeoCDg3x+f36Bg3iEen+GfH+Bgn57en+GfYaCeIeBgH5+g31/gniAeYKFfYZ5hnt9h4V6foJ8gH6DfIJ9hHp8iXeEgXx6goB4hoN9fXuIh318f4VzgIR7jXl5g4WEhnx9fYWCeXmAfH98gIWFfXx7e4WDgX2FgHqCf4B/eH98hoeEeoSFenmEhXt8g3x5gn+Efn1+hnWCg4aBgIN+dIKEfYZ/fn17hXyEeIeAe3t+iH15f4OCeoCLdod8fod1fIB6fYZ/hYaCfXp7foB9g32BgIN/goJ8iYN7fXl6e4GKhHuDhnZ9goZ5hHeGe4J3gYKChIN4dn+HeYR7iIJ4i32BfIN7e4KBdn+FgHt4hH2EfnqEhHyHgIF9fYSGfHt5h3uAgIGDe3t8hIWLfIWCcniDgnuIgHx+eX99gIOGgYeGfXl3gXyAg3yFgnV/hH+FdnqBhXmJfX2Ke4h6d399foSIeYh7fnyBg3uKf3x+eYCAg4N9doeAgIOBg3l+h4Z3hYZ8e4CCfH6Cf4GDfX58f3aJhXR9i315eXyAiH17i32Jf3iDfX2FgH57gICFhXp/e3mKgXqBhX6Hhn2GZmmVh2lukoZ8gYpnjoOJgntkgI2EhWCOiXJ7jm+TeHyId22KfoGGgZJ/c3yBi350en1/dnGQiXaOkHVyio9nf3iJenmRaYp5kJOBjF+Li2h0hYR6gnuGfoeFcoV+j3R7fo9pjXyKh3SHfHeMcodzeomFfG6LfnmLg4OFbol6bpGFe4WJg4Nwd4GBd36EfHp+iH+Dg3SCi3x8gH91hYh2g32Heot4d4eIgneBfX57hH+EeIB+eoN6joCCfoF+fn6KeoCEeYOHe4B+eX2DhoN6gId4fod/fIN3gIF6iH5+hHyAgIB8eoeDdYGEgnl8gHx7g4V+hYJ5i3l5e36CiIGCenmDgX9/hIF7foZ8f4GBhHx1h3eBgYd/eICAgoR9gYh7e32Af3l9gYF4inaCfYqFeYF+e4OGgnSIdY2GeneGeXuDiIF8eoGHfH6Fc4l6f4eDeX97goWEfnSBfYSJfIZ8fX2BdYl7eIB9hIR+foh7eIZ/foWDeX56goCFgH+Eeod9f3l9goZ7fYJ/e32EiX2Ag4GFdX6GgXx7fYODgnl9foGBg35+doOBgnuEiXR+g3+Afn5+g4N9g3+DeYN4hX55hoiDfHaAhIN/e319foJ/g4CAg394hYF+hHx7hn56fYKBfYWGfnN8g3yAgn+IeH+DfX9+gXmGgoR8g3uAf4aBdn6KeX9+foB+f4J/f4SAhHx3fX2DgIOFf359g3mHfIKCgH14fIODhHl/hIZ8g39/fXl/goaDenqBf3yDen+ChX+EgHeCgX97g4Z+hIB+fnqEfIN+gniGgH6CeIF/eX6GfYKBgHyFgoGBfHp7hoF8fod/d4SDfn2Bfn6Dhnd/gH19h4SEgXl6fnyAgn6AfoGAhXyAgX57gXqHf4J+eoKEg32EgnuCe4N8fH6GeoF9gIOBfoB4fYV+g36GgHt8foKAhX59fH6AfoOEfH2DfYWCgniCfoF/gH59foh9d3+DgYGEfn2BeX6GfXyAgoKGg3mBgn58g4F5gH97hX59f4F/goGBe399hn+AfoJ/fYF4f4N+f4GAe4d7fYF+g3qEgXx/iIN4hYV/eYKAgX98g3x7f4GAf36CfYF/e4eBfn1/fYOBg31/hH2AfoKDf316foGCgYR7fX+De4J4gYd7gn2DhHx+goF7gYGAeXyFfnyBgX5+gn18f4WCgX+Df4B9gn6BgH5/f36Dfn6GeIN8gYCBfICCfIN/gYGEenuBgYR3fYGAgYGAfn+BgHx9f4Z6goN9fIOHfX5+f4B6gX6DgoF+hIF5gX2BgX18f4GCfYB/fnyCg4F9g31/hIODfX1+foKBfX6AeX1+hIGEgH+Cgnx/fn2EfIR+fX1+g36AgXx/goKFfXt7gX2BgIh8e3+AhYF7gnyAg4OCeX97gYCAfoSAfXqAhnx9hIJ6gYOCe4J7gn2AfoKBfYB+gYKAfX5/f4B8hX2FgIN+fnmEgIGBfoF/foN+fnqDfn+AfYB/gYF7gn99foCAgYOBgH2Cfn6Cfn98f4GFe36BgoN8f4CAgIB/fYCBg3h+gH+AgIN9gIGAgH19gYGCgH9/f3+AgH2Df36Egn2BeYF8gIGCgX2Ag4F+f39/fX6Df35/gIB/gX9+goF8f4CDe3x/goJ/f4B/f3+Af4B/fYCEfoJ+gX2Af32Cgn9+fn5+gICAgoN9f319f4OBgn9+f36AgoCAgoF+fnt/goF+fX+Cfn5/fn+Cg4B8f4F/gH6AgHyDgn5+f35/gIB/gn9+gX19goF/gH5/gH9/fYJ/f4F9gIKCgn9+f319f35/gYB+goKBf31/gICBgXuDfn5/f4J+gH+BgHyAgIGAf39+fIGBgH9/f3+AgH9/gX6Af4CBgoB7f4KBf39/fYGCgX59fX+AgYB/gYB/f3+BgX6AfX6Df4F/f4CAfYGAgn2Bfn9/f4GBf4CBgH9/fn5/goCAfYCAf39/f4CCgH9/gH+Afn+AgoB+gICAgH9/gX5/f3+Af4KBfn9+gX1/goCAfICAgX2Bf39/gICAgIF/gH9/f4F/gH+Afn+AfYB/f4CBfoCBfn+AgIB/f39+gH6BgH2BgX6AgX2Af39/gIF/gYB+gH+Af4F9f4CAgH+Af3+BgH6Af39/f4N/fn+AgYB+gH+AgIB+foCBfn+AgX+Bfn9/gICAf39/gYF/gH9/gYB/gH9/f4B/f4CAgICBgH6Bf4CAfoB/f4CAf35/gICAgIB+f36AgYCAgH+Af35/f4F/gIB+f4B/gIGAf4B/f4B/f4B/gIB/f4CBf3+Af3+Bf39/gH9/gH+Af4CAgH+AgH9/gH9/gICAgIB/f4B/gICAgH9/gH+Af4B/gH+Af3+Af4B/gH+Af4CAf4CAgIB/gIB/f4CAgIB/f4B/f4CAf4B/f4CAgH9/f4B/gIB/f3+AgIB/gIB/gH+Af39/gIB/f4CAgH+AgH9/f39/f4CAf3+AgIB/f4CAgH+AgH+Af3+Af4B/f39/gICAf3+Af3+Af4CAf4CAf4CAgH+AgA==';
};

// Play sound when long pressing a message
export const playLongPressSound = async () => {
  try {
    const audio = new Audio();
    audio.src = generateLongPressSound();
    audio.volume = 0.1; // Much lower volume for subtle feedback

    const playPromise = audio.play();
    if (playPromise !== undefined) {
      await playPromise;
      console.log('Long press sound played');
    }
  } catch (error) {
    console.log('Long press sound failed:', error);
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
