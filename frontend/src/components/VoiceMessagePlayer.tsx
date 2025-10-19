'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause } from 'lucide-react';

interface VoiceMessagePlayerProps {
  voiceUrl: string;
  duration: number;
  waveformData: number[];
  className?: string;
  isMyMessage?: boolean;
  voicePlayButton?: string;
  voicePlayIconColor?: string;
  voiceWaveformActive?: string;
  voiceWaveformInactive?: string;
  durationTextColor?: string;
}

// Global audio manager to ensure only one audio plays at a time
class GlobalAudioManager {
  private static currentAudio: HTMLAudioElement | null = null;
  private static currentStopCallback: (() => void) | null = null;

  static play(audio: HTMLAudioElement, stopCallback: () => void) {
    // Stop any currently playing audio
    if (this.currentAudio && this.currentAudio !== audio) {
      this.currentAudio.pause();
      if (this.currentStopCallback) {
        this.currentStopCallback();
      }
    }
    this.currentAudio = audio;
    this.currentStopCallback = stopCallback;
  }

  static stop(audio: HTMLAudioElement) {
    if (this.currentAudio === audio) {
      this.currentAudio = null;
      this.currentStopCallback = null;
    }
  }
}

export default function VoiceMessagePlayer({
  voiceUrl,
  duration,
  waveformData,
  className = '',
  isMyMessage = false,
  voicePlayButton = 'bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600',
  voicePlayIconColor = 'white',
  voiceWaveformActive = 'bg-gradient-to-t from-purple-500 to-blue-500',
  voiceWaveformInactive = 'bg-gray-400 dark:bg-gray-500',
  durationTextColor = 'text-gray-500 dark:text-gray-400'
}: VoiceMessagePlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const srcSetRef = useRef<boolean>(false); // Track if we've explicitly set the src

  // Tailwind safelist: Ensure these dynamic classes from database are generated
  // bg-slate-700 hover:bg-slate-800 active:bg-slate-900 bg-slate-800 bg-slate-800/50
  // bg-zinc-800 hover:bg-zinc-900 active:bg-black bg-zinc-950 bg-zinc-950/60
  // text-white text-yellow-950 text-gray-900

  // Initialize audio element
  useEffect(() => {
    if (!voiceUrl) {
      console.warn('[VoiceMessagePlayer] No voice URL provided');
      return;
    }

    // Create audio WITHOUT source initially (iOS Safari workaround)
    // Setting src will happen lazily when user clicks play
    const audio = new Audio();
    audioRef.current = audio;
    srcSetRef.current = false; // Reset the flag

    audio.addEventListener('ended', () => {
      setIsPlaying(false);
      setCurrentTime(0);
    });

    // Only log errors if we've explicitly set the src (avoid logging errors from empty audio element)
    audio.addEventListener('error', (e) => {
      if (srcSetRef.current) {
        console.error('[VoiceMessagePlayer] Audio load error for URL:', voiceUrl, e);
        setIsPlaying(false);
      }
    });

    audio.addEventListener('loadedmetadata', () => {
      console.log('[VoiceMessagePlayer] Audio loaded successfully, duration:', audio.duration);
    });

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      audio.pause();
      audio.src = '';
      srcSetRef.current = false;
    };
  }, [voiceUrl]);

  // Update current time while playing
  useEffect(() => {
    if (!isPlaying || !audioRef.current) {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      return;
    }

    const updateTime = () => {
      if (audioRef.current) {
        setCurrentTime(audioRef.current.currentTime);
        animationFrameRef.current = requestAnimationFrame(updateTime);
      }
    };

    animationFrameRef.current = requestAnimationFrame(updateTime);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPlaying]);

  const togglePlayPause = async () => {
    console.log('[VoiceMessagePlayer] 🎵 togglePlayPause called for URL:', voiceUrl);

    if (!audioRef.current) {
      console.error('[VoiceMessagePlayer] ❌ audioRef.current is null! Cannot play audio.');
      return;
    }

    try {
      if (isPlaying) {
        console.log('[VoiceMessagePlayer] ⏸️ Pausing audio');
        audioRef.current.pause();
        setIsPlaying(false);
        GlobalAudioManager.stop(audioRef.current);
      } else {
        console.log('[VoiceMessagePlayer] ▶️ Attempting to play audio...');

        // iOS Safari workaround: Set src lazily on first play
        // This avoids preload issues that can cause readyState to stay at 0
        if (!srcSetRef.current) {
          console.log('[VoiceMessagePlayer] 🔗 Setting audio src on first play (iOS workaround)');
          // Voice URLs are already relative URLs (e.g., /media/...)
          // Next.js server.js proxies /media/ requests to backend
          console.log('[VoiceMessagePlayer] 🔗 URL:', voiceUrl);
          audioRef.current.src = voiceUrl;
          srcSetRef.current = true; // Mark that we've set the source
        }

        console.log('[VoiceMessagePlayer] 🎵 Audio element state:', {
          src: audioRef.current.src,
          readyState: audioRef.current.readyState,
          networkState: audioRef.current.networkState,
          error: audioRef.current.error,
        });

        // iOS Safari requires the audio to have loaded enough data before playing
        // readyState 0 = HAVE_NOTHING (no data loaded)
        // readyState 1+ = HAVE_METADATA or better (can start playing)
        if (audioRef.current.readyState === 0) {
          console.log('[VoiceMessagePlayer] ⏳ Audio not loaded yet (readyState=0), calling load()...');
          audioRef.current.load(); // Force reload the audio

          // Wait for metadata to load before playing
          await new Promise<void>((resolve, reject) => {
            const audio = audioRef.current!;
            const onCanPlay = () => {
              console.log('[VoiceMessagePlayer] ✅ Audio loaded, readyState:', audio.readyState);
              audio.removeEventListener('canplay', onCanPlay);
              audio.removeEventListener('error', onError);
              resolve();
            };
            const onError = (e: Event) => {
              console.error('[VoiceMessagePlayer] ❌ Audio load error:', e);
              audio.removeEventListener('canplay', onCanPlay);
              audio.removeEventListener('error', onError);
              reject(new Error('Failed to load audio'));
            };
            audio.addEventListener('canplay', onCanPlay);
            audio.addEventListener('error', onError);
          });
        }

        // Register with global manager before playing
        GlobalAudioManager.play(audioRef.current, () => {
          console.log('[VoiceMessagePlayer] 🛑 GlobalAudioManager called stop callback');
          setIsPlaying(false);
        });

        console.log('[VoiceMessagePlayer] 🔊 Calling audio.play()...');
        await audioRef.current.play();
        console.log('[VoiceMessagePlayer] ✅ Audio.play() succeeded!');
        setIsPlaying(true);
      }
    } catch (error) {
      console.error('[VoiceMessagePlayer] ❌ Playback error:', error);
      console.error('[VoiceMessagePlayer] ❌ Error details:', {
        name: (error as Error).name,
        message: (error as Error).message,
        audioSrc: audioRef.current?.src,
        audioReadyState: audioRef.current?.readyState,
      });
      setIsPlaying(false);
    }
  };

  const handleWaveformClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!audioRef.current) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percentage = clickX / rect.width;
    const newTime = percentage * duration;

    audioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const formatTime = (seconds: number): string => {
    if (!isFinite(seconds) || seconds < 0) {
      return '0:00';
    }
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Use the duration from the database prop instead of audio.duration
  // This fixes iOS Safari WebM metadata parsing issues
  const actualDuration = duration > 0 && isFinite(duration) ? duration : (audioRef.current?.duration || 0);
  const progress = actualDuration > 0 ? currentTime / actualDuration : 0;

  // Always normalize to exactly 50 bars for consistent width
  const FIXED_BAR_COUNT = 50;

  // Ensure we have valid waveform data, fallback to default pattern if missing
  let displayWaveform: number[];
  if (waveformData && waveformData.length > 0) {
    // Resample to exactly 50 bars
    if (waveformData.length === FIXED_BAR_COUNT) {
      displayWaveform = waveformData;
    } else if (waveformData.length < FIXED_BAR_COUNT) {
      // Upsample by repeating values
      displayWaveform = [];
      const ratio = FIXED_BAR_COUNT / waveformData.length;
      for (let i = 0; i < FIXED_BAR_COUNT; i++) {
        const sourceIndex = Math.floor(i / ratio);
        displayWaveform.push(waveformData[sourceIndex]);
      }
    } else {
      // Downsample by averaging chunks
      displayWaveform = [];
      const chunkSize = waveformData.length / FIXED_BAR_COUNT;
      for (let i = 0; i < FIXED_BAR_COUNT; i++) {
        const start = Math.floor(i * chunkSize);
        const end = Math.floor((i + 1) * chunkSize);
        let sum = 0;
        for (let j = start; j < end; j++) {
          sum += waveformData[j];
        }
        displayWaveform.push(sum / (end - start));
      }
    }
  } else {
    // Fallback: random pattern
    displayWaveform = Array(FIXED_BAR_COUNT).fill(0).map(() => Math.random() * 0.8 + 0.2);
  }

  // Debug logging removed - component renders multiple times during page load which is normal React behavior

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {/* Play/Pause Button */}
      <button
        onClick={togglePlayPause}
        className={`flex-shrink-0 w-8 h-8 rounded-full transition-all flex items-center justify-center shadow-sm ${voicePlayButton}`}
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? (
          <Pause size={13} className={voicePlayIconColor} fill="currentColor" strokeWidth={0} />
        ) : (
          <Play size={13} className={`${voicePlayIconColor} ml-0.5`} fill="currentColor" strokeWidth={0} />
        )}
      </button>

      {/* Waveform Visualization - Fixed width */}
      <div
        className="h-8 flex items-center gap-[1px] cursor-pointer"
        style={{ width: '150px' }}
        onClick={handleWaveformClick}
      >
        {displayWaveform.map((amplitude, index) => {
          const barProgress = index / displayWaveform.length;
          const isActive = barProgress <= progress;
          // Use square root to expand variation (makes quiet sounds quieter, loud sounds louder)
          const enhancedAmplitude = Math.sqrt(amplitude);
          const height = Math.max(4, enhancedAmplitude * 40); // Min 4px, max 40px

          return (
            <div
              key={index}
              className={`w-[2px] rounded-full transition-colors ${
                isActive ? voiceWaveformActive : voiceWaveformInactive
              }`}
              style={{ height: `${height}px` }}
            />
          );
        })}
      </div>

      {/* Time Display */}
      <div className={`flex-shrink-0 text-[11px] font-mono tabular-nums min-w-[32px] text-right ${durationTextColor}`}>
        {formatTime(isPlaying ? currentTime : actualDuration)}
      </div>
    </div>
  );
}
