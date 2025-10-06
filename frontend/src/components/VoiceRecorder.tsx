'use client';

import React, { useState, useRef, useEffect } from 'react';
import { flushSync } from 'react-dom';
import { Mic, Square, Play, Trash2 } from 'lucide-react';
import { WaveformAnalyzer, downsampleWaveform, type RecordingMetadata } from '@/lib/waveform';

interface VoiceRecorderProps {
  onRecordingComplete: (audioBlob: Blob, metadata: RecordingMetadata) => void;
  onRecordingReady?: (hasRecording: boolean) => void;
  disabled?: boolean;
  className?: string;
}

type RecordingState = 'idle' | 'recording' | 'preview';

export default function VoiceRecorder({ onRecordingComplete, onRecordingReady, disabled, className }: VoiceRecorderProps) {
  const [recordingState, setRecordingState] = useState<RecordingState>('idle');
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [recordingMetadata, setRecordingMetadata] = useState<RecordingMetadata | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const waveformAnalyzerRef = useRef<WaveformAnalyzer | null>(null);
  const recordingStartTimeRef = useRef<number>(0);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
      if (waveformAnalyzerRef.current) {
        waveformAnalyzerRef.current.dispose();
      }
    };
  }, [audioUrl]);

  // Notify parent when recording state changes
  useEffect(() => {
    if (onRecordingReady) {
      onRecordingReady(recordingState === 'preview' && !!audioBlob && !!recordingMetadata);
    }
  }, [recordingState, audioBlob, recordingMetadata, onRecordingReady]);

  const startRecording = async () => {
    const startTime = performance.now();
    console.log('[VoiceRecorder] ⏱️ START - Recording button clicked at t=0ms');

    try {
      // Check if already recording
      if (recordingState === 'recording') {
        return;
      }

      // Check if getUserMedia is available
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert('Microphone access is not available in your browser.');
        return;
      }

      // Check if MediaRecorder exists
      if (typeof MediaRecorder === 'undefined') {
        alert('MediaRecorder API is not available in your browser.');
        return;
      }

      // CRITICAL CLEANUP ORDER (matches MessagingApp exactly):
      // 1. Stop stream tracks FIRST (disconnect from AudioContext)
      // 2. Close AudioContext SECOND (after stream is disconnected)
      // 3. Clean up MediaRecorder
      // This prevents iOS Safari from getting confused about audio resources

      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - Starting cleanup...`);

      // Step 1: Stop stream tracks first
      if (streamRef.current) {
        console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - Stopping old stream tracks...`);
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }

      // Step 2: Clean up MediaRecorder
      if (mediaRecorderRef.current) {
        if (mediaRecorderRef.current.state === 'recording') {
          mediaRecorderRef.current.stop();
        }
        mediaRecorderRef.current = null;
      }

      // Step 3: Close AudioContext LAST (after stream is disconnected)
      if (audioContextRef.current) {
        console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - Closing old AudioContext...`);
        await audioContextRef.current.close();
        console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - Old AudioContext closed successfully`);
        audioContextRef.current = null;
      }

      // Simple constraints - iOS Safari works best with this
      const constraints = {
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      };

      // Request microphone access with timeout detection
      // iOS Safari sometimes takes 10+ seconds to return getUserMedia, which then gets killed immediately
      // If it takes more than 3 seconds, something is wrong - abort and show error
      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - Requesting microphone access...`);

      const getUserMediaStart = performance.now();
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      const getUserMediaDuration = Math.round(performance.now() - getUserMediaStart);

      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - Microphone access granted, stream obtained (took ${getUserMediaDuration}ms)`);

      // If getUserMedia took more than 3 seconds, iOS is likely going to kill the stream
      // Stop it immediately and show error instead of letting user experience a broken recording
      if (getUserMediaDuration > 3000) {
        console.error(`[VoiceRecorder] ⚠️ getUserMedia took ${getUserMediaDuration}ms (>3s) - iOS Safari will likely kill this stream. Aborting.`);
        stream.getTracks().forEach(track => track.stop());
        alert('Microphone access took too long. This is an iOS Safari issue. Please try recording again.');
        setRecordingState('idle');
        return;
      }

      streamRef.current = stream;

      // CRITICAL: Immediately create NEW AudioContext and connect stream
      // This tells iOS Safari we're actively using the microphone - keeps stream alive!
      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - Creating AudioContext to keep stream alive...`);
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioContextRef.current = audioContext;
      const microphone = audioContext.createMediaStreamSource(stream);
      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - AudioContext created, stream actively being used`);

      // Initialize waveform analyzer to capture amplitude data
      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - Creating WaveformAnalyzer...`);
      const waveformAnalyzer = new WaveformAnalyzer(stream, 50); // Target 50 samples
      waveformAnalyzerRef.current = waveformAnalyzer;
      waveformAnalyzer.start();
      recordingStartTimeRef.current = Date.now();
      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - WaveformAnalyzer started`);

      // CRITICAL: Detect when iOS Safari kills the microphone stream
      stream.getTracks().forEach(track => {
        track.onended = () => {
          const killedAt = Math.round(performance.now() - startTime);
          console.error(`[VoiceRecorder] ⏱️ ❌ MICROPHONE KILLED at t=${killedAt}ms - iOS Safari terminated the stream!`);
        };
      });

      // Create MediaRecorder with iOS-compatible codec
      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - Creating MediaRecorder...`);

      // iOS Safari CRITICAL FIX: Must use audio/mp4 with AAC codec
      // WebM/Opus (default on iOS) cannot be played back on iOS itself!
      // Desktop Chrome can play WebM, but iOS cannot.
      let mimeType = 'audio/webm;codecs=opus'; // Default for desktop

      if (MediaRecorder.isTypeSupported('audio/mp4')) {
        // iOS Safari supports audio/mp4 recording AND playback
        mimeType = 'audio/mp4';
        console.log('[VoiceRecorder] ✅ Using audio/mp4 (iOS-compatible)');
      } else if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
        console.log('[VoiceRecorder] ⚠️ Using audio/webm;codecs=opus (desktop)');
      } else {
        console.warn('[VoiceRecorder] ⚠️ No preferred codec supported, using browser default');
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      console.log('[VoiceRecorder] 📝 MediaRecorder mimeType:', mediaRecorder.mimeType);

      // Set handlers BEFORE starting
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
          console.log('[VoiceRecorder] Data chunk received, size:', event.data.size);
        }
      };

      mediaRecorder.onstop = () => {
        console.log('[VoiceRecorder] MediaRecorder onstop fired');
        const blob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType });
        console.log('[VoiceRecorder] 📦 Created blob with type:', blob.type, 'size:', blob.size);
        const url = URL.createObjectURL(blob);

        // Capture waveform data and duration
        let metadata: RecordingMetadata | null = null;
        if (waveformAnalyzerRef.current) {
          const waveformData = waveformAnalyzerRef.current.stop();
          const duration = (Date.now() - recordingStartTimeRef.current) / 1000; // Convert to seconds

          // Downsample to ~50 bars for consistent visualization
          const downsampledWaveform = downsampleWaveform(waveformData.amplitudes, 50);

          metadata = {
            duration,
            waveformData: downsampledWaveform
          };

          console.log('[VoiceRecorder] Captured metadata:', {
            duration: metadata.duration.toFixed(2),
            waveformSamples: metadata.waveformData.length
          });
        }

        console.log('[VoiceRecorder] Setting preview state with blob size:', blob.size);
        setAudioBlob(blob);
        setAudioUrl(url);
        setRecordingMetadata(metadata);
        setRecordingState('preview');

        if (streamRef.current) {
          console.log('[VoiceRecorder] Stopping stream tracks');
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }

        if (timerRef.current) {
          clearInterval(timerRef.current);
        }
      };

      // CRITICAL: Start MediaRecorder IMMEDIATELY (before UI updates!)
      // iOS Safari requires this to happen ASAP after AudioContext creation
      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - Starting MediaRecorder NOW`);
      mediaRecorder.start(100);
      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - MediaRecorder started, state:`, mediaRecorder.state);

      // Update UI state AFTER starting (use flushSync for immediate render)
      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - Updating UI state after MediaRecorder start`);
      flushSync(() => {
        setRecordingTime(0);
        setRecordingState('recording');
      });
      console.log(`[VoiceRecorder] ⏱️ t=${Math.round(performance.now() - startTime)}ms - ✅ UI state updated - Recording UI should be visible now`);

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);

    } catch (error: any) {
      console.error('Error accessing microphone:', error);

      // Reset state on error
      setRecordingState('idle');
      setRecordingTime(0);
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }

      if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        alert('Microphone permission denied. Please allow microphone access and try again.');
      } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        alert('No microphone found. Please connect a microphone and try again.');
      } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
        alert('Microphone is already in use by another application.');
      } else {
        alert(`Could not access microphone: ${error.message || 'Unknown error'}`);
      }
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && recordingState === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  const playRecording = () => {
    if (!audioUrl) return;

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setIsPlaying(false);
    }

    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    audio.onended = () => {
      setIsPlaying(false);
      audioRef.current = null;
    };

    audio.play();
    setIsPlaying(true);
  };

  const deleteRecording = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }

    setAudioBlob(null);
    setAudioUrl(null);
    setRecordingMetadata(null);
    setRecordingTime(0);
    setIsPlaying(false);
    setRecordingState('idle');
    chunksRef.current = [];
  };

  // Expose send method for parent to call
  const sendRecording = () => {
    if (!audioBlob || !recordingMetadata) return;

    // Call parent callback with the blob and metadata
    onRecordingComplete(audioBlob, recordingMetadata);

    // Reset to idle state
    deleteRecording();
  };

  // Expose send method to parent via a method they can call
  useEffect(() => {
    (window as any).__voiceRecorderSendMethod = sendRecording;
    return () => {
      delete (window as any).__voiceRecorderSendMethod;
    };
  }, [audioBlob, recordingMetadata]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {recordingState === 'idle' && (
        <button
          type="button"
          onClick={startRecording}
          disabled={disabled}
          className="p-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          title="Record voice message"
        >
          <Mic size={20} />
        </button>
      )}

      {recordingState === 'recording' && (
        <>
          <button
            onClick={stopRecording}
            className="p-2 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
            title="Stop recording"
          >
            <Square size={18} fill="white" />
          </button>
          <div className="flex items-center gap-1.5">
            <div className="flex gap-0.5">
              {[...Array(3)].map((_, i) => (
                <div
                  key={i}
                  className="w-0.5 bg-red-500 rounded-full animate-pulse"
                  style={{
                    height: '10px',
                    animationDelay: `${i * 150}ms`,
                  }}
                />
              ))}
            </div>
            <span className="text-xs font-mono text-red-500">{formatTime(recordingTime)}</span>
          </div>
        </>
      )}

      {recordingState === 'preview' && (
        <>
          <button
            type="button"
            onClick={playRecording}
            className="p-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700 transition-all"
            title="Play recording"
          >
            <Play size={18} fill={isPlaying ? 'white' : 'none'} strokeWidth={isPlaying ? 0 : 2} />
          </button>
          <span className="text-xs font-mono text-gray-600 dark:text-gray-400">
            {formatTime(recordingTime)}
          </span>
          <button
            type="button"
            onClick={deleteRecording}
            className="p-2 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
            title="Delete recording"
          >
            <Trash2 size={18} />
          </button>
        </>
      )}
    </div>
  );
}
