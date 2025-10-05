'use client';

import React, { useState, useRef, useEffect } from 'react';
import { flushSync } from 'react-dom';
import { Mic, Square, Loader2, Play, Trash2, Send } from 'lucide-react';

interface VoiceRecorderProps {
  onRecordingComplete: (audioBlob: Blob) => void;
  disabled?: boolean;
  className?: string;
}

type RecordingState = 'idle' | 'recording' | 'preview';

export default function VoiceRecorder({ onRecordingComplete, disabled, className }: VoiceRecorderProps) {
  const [recordingState, setRecordingState] = useState<RecordingState>('idle');
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  const startRecording = async () => {
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

      // Clean up any existing stream and recorder (initialize fresh state)
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }

      if (mediaRecorderRef.current) {
        if (mediaRecorderRef.current.state === 'recording') {
          mediaRecorderRef.current.stop();
        }
        mediaRecorderRef.current = null;
      }

      // Simple constraints - iOS Safari works best with this
      const constraints = {
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      };

      // Request microphone access (fresh stream each time)
      console.log('[VoiceRecorder] Requesting microphone access...');
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      console.log('[VoiceRecorder] Microphone access granted, stream obtained');
      streamRef.current = stream;

      // CRITICAL: Immediately create AudioContext and connect stream
      // This tells iOS Safari we're actively using the microphone - keeps stream alive!
      console.log('[VoiceRecorder] Creating AudioContext to keep stream alive...');
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const microphone = audioContext.createMediaStreamSource(stream);
      console.log('[VoiceRecorder] AudioContext created, stream actively being used');

      // Create MediaRecorder
      console.log('[VoiceRecorder] Creating MediaRecorder...');
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      // Set handlers BEFORE starting
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
          console.log('[VoiceRecorder] Data chunk received, size:', event.data.size);
        }
      };

      mediaRecorder.onstop = () => {
        console.log('[VoiceRecorder] MediaRecorder onstop fired');
        const blob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType || 'audio/webm' });
        const url = URL.createObjectURL(blob);

        console.log('[VoiceRecorder] Setting preview state with blob size:', blob.size);
        setAudioBlob(blob);
        setAudioUrl(url);
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

      // Update UI state FIRST using flushSync for IMMEDIATE synchronous render
      // This forces React to update the DOM RIGHT NOW, not in the next tick
      console.log('[VoiceRecorder] Setting recording state to recording (IMMEDIATE with flushSync)');
      flushSync(() => {
        setRecordingTime(0);
        setRecordingState('recording');
      });
      console.log('[VoiceRecorder] UI state updated, DOM rendered');

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);

      // Now start MediaRecorder IMMEDIATELY (iOS Safari requires this!)
      console.log('[VoiceRecorder] Starting MediaRecorder NOW');
      mediaRecorder.start(100);
      console.log('[VoiceRecorder] MediaRecorder started, state:', mediaRecorder.state);

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
    setRecordingTime(0);
    setIsPlaying(false);
    setRecordingState('idle');
    chunksRef.current = [];
  };

  const sendRecording = () => {
    if (!audioBlob) return;

    // Call parent callback with the blob
    onRecordingComplete(audioBlob);

    // Reset to idle state
    deleteRecording();
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={className}>
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
        <div className="flex items-center gap-2 px-3 py-2 bg-red-500 text-white rounded-lg">
          <button
            onClick={stopRecording}
            className="hover:bg-red-600 rounded p-1 transition-colors"
            title="Stop recording"
          >
            <Square size={20} fill="white" />
          </button>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {[...Array(3)].map((_, i) => (
                <div
                  key={i}
                  className="w-1 bg-white rounded-full animate-pulse"
                  style={{
                    height: '12px',
                    animationDelay: `${i * 150}ms`,
                  }}
                />
              ))}
            </div>
            <span className="text-sm font-mono">{formatTime(recordingTime)}</span>
          </div>
        </div>
      )}

      {recordingState === 'preview' && (
        <div className="flex items-center gap-2 p-2 bg-gradient-to-r from-purple-100 to-blue-100 dark:from-purple-900/30 dark:to-blue-900/30 rounded-lg">
          <button
            onClick={playRecording}
            className="p-2 rounded-lg bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            title="Play recording"
          >
            <Play size={18} fill={isPlaying ? 'currentColor' : 'none'} />
          </button>
          <span className="text-sm font-mono text-gray-700 dark:text-gray-300">
            {formatTime(recordingTime)}
          </span>
          <div className="flex gap-1 ml-auto">
            <button
              onClick={deleteRecording}
              className="p-2 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
              title="Delete recording"
            >
              <Trash2 size={18} />
            </button>
            <button
              onClick={sendRecording}
              className="p-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700 transition-all"
              title="Send voice message"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
