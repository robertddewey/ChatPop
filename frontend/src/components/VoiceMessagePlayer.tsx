'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause } from 'lucide-react';

interface VoiceMessagePlayerProps {
  voiceUrl: string;
  duration: number;
  waveformData: number[];
  className?: string;
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
  className = ''
}: VoiceMessagePlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Initialize audio element
  useEffect(() => {
    if (!voiceUrl) {
      console.warn('[VoiceMessagePlayer] No voice URL provided');
      return;
    }

    const audio = new Audio();
    audioRef.current = audio;

    audio.addEventListener('ended', () => {
      setIsPlaying(false);
      setCurrentTime(0);
    });

    audio.addEventListener('error', (e) => {
      console.error('[VoiceMessagePlayer] Audio load error for URL:', voiceUrl, e);
      setIsPlaying(false);
    });

    audio.addEventListener('loadedmetadata', () => {
      console.log('[VoiceMessagePlayer] Audio loaded successfully, duration:', audio.duration);
    });

    // Set the source after setting up event listeners
    audio.src = voiceUrl;

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      audio.pause();
      audio.src = '';
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
    if (!audioRef.current) return;

    try {
      if (isPlaying) {
        audioRef.current.pause();
        setIsPlaying(false);
        GlobalAudioManager.stop(audioRef.current);
      } else {
        // Register with global manager before playing
        GlobalAudioManager.play(audioRef.current, () => {
          setIsPlaying(false);
        });
        await audioRef.current.play();
        setIsPlaying(true);
      }
    } catch (error) {
      console.error('[VoiceMessagePlayer] Playback error:', error);
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

  const progress = duration > 0 && isFinite(duration) ? currentTime / duration : 0;

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

  console.log('[VoiceMessagePlayer] Render - duration:', duration, 'waveformData length:', waveformData?.length, 'displayWaveform length:', displayWaveform.length, 'voiceUrl:', voiceUrl);

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {/* Play/Pause Button */}
      <button
        onClick={togglePlayPause}
        className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 transition-all flex items-center justify-center text-white shadow-sm"
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? (
          <Pause size={13} fill="white" strokeWidth={0} />
        ) : (
          <Play size={13} fill="white" strokeWidth={0} className="ml-0.5" />
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
                isActive
                  ? 'bg-gradient-to-t from-purple-500 to-blue-500'
                  : 'bg-gray-400 dark:bg-gray-500'
              }`}
              style={{ height: `${height}px` }}
            />
          );
        })}
      </div>

      {/* Time Display */}
      <div className="flex-shrink-0 text-[11px] text-gray-500 dark:text-gray-400 font-mono tabular-nums min-w-[32px] text-right">
        {formatTime(isPlaying ? currentTime : duration)}
      </div>
    </div>
  );
}
