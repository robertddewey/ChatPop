'use client';

import React, { useState, useRef, useEffect } from 'react';
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
  const streamRef = useRef<MediaStream | null>(null); // Keep stream alive
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
      // Clean up stream on unmount
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, [audioUrl]);

  const startRecording = async () => {
    try {
      console.log('=== Voice Recording Debug ===');
      console.log('MediaRecorder available:', typeof MediaRecorder !== 'undefined');
      console.log('navigator.mediaDevices available:', !!navigator.mediaDevices);
      console.log('navigator.mediaDevices.getUserMedia available:', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));
      console.log('Current URL:', window.location.href);
      console.log('Is secure context:', window.isSecureContext);

      // Check if getUserMedia is available
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        const isIP = /^\d+\.\d+\.\d+\.\d+/.test(window.location.hostname);
        if (isIP && !window.isSecureContext) {
          alert('Voice recording requires HTTPS when accessing via IP address.\n\nPlease access via:\n• localhost:4000 on this device, or\n• Use HTTPS, or\n• Test on desktop browser first');
        } else {
          alert('Microphone access is not available in your browser. Please try a different browser or update iOS.');
        }
        return;
      }

      // Check if MediaRecorder exists
      if (typeof MediaRecorder === 'undefined') {
        console.error('MediaRecorder not available');
        alert('MediaRecorder API is not available in your browser. Voice recording requires iOS 14.3+ or a different browser.');
        return;
      }

      // Reuse existing stream if available, otherwise request new one
      let stream = streamRef.current;

      if (!stream || !stream.active) {
        console.log('Requesting microphone permission...');

        // iOS Safari workaround: Try simple audio: true first
        // Complex constraints can cause the AVAudioSessionCaptureDevice error
        let constraints: any = { audio: true };

        // Retry logic for iOS Safari bug
        let retries = 0;
        const maxRetries = 2;

        while (retries <= maxRetries) {
          try {
            if (retries > 0) {
              console.log(`Retry attempt ${retries}/${maxRetries}...`);
              // Wait before retry
              await new Promise(resolve => setTimeout(resolve, 500));
            }

            stream = await navigator.mediaDevices.getUserMedia(constraints);
            console.log('Microphone access granted, stream:', stream);
            console.log('Stream active:', stream.active);
            console.log('Stream tracks:', stream.getTracks().map(t => ({ kind: t.kind, enabled: t.enabled, readyState: t.readyState })));

            // Success! Break out of retry loop
            break;
          } catch (err: any) {
            console.log(`getUserMedia attempt ${retries + 1} failed:`, err.message);

            if (retries === maxRetries) {
              // All retries exhausted, throw the error
              throw err;
            }

            retries++;
          }
        }

        // Store stream reference to keep it alive across recordings
        streamRef.current = stream;

        // iOS Safari: Wait for audio session to fully initialize
        // The "No AVAudioSessionCaptureDevice" error happens when iOS hasn't
        // fully set up the audio capture device yet
        console.log('Waiting for iOS audio session to initialize...');
        await new Promise(resolve => setTimeout(resolve, 300));
        console.log('Audio session initialized, ready to record');
      } else {
        console.log('Reusing existing microphone stream');
      }

      // Determine MIME type - try to find a supported type
      let mimeType = '';
      const types = [
        'audio/webm',
        'audio/webm;codecs=opus',
        'audio/mp4',
        'audio/mp4;codecs=mp4a',
        'audio/mpeg',
        'audio/wav',
      ];

      for (const type of types) {
        if (MediaRecorder.isTypeSupported(type)) {
          mimeType = type;
          console.log('Using MIME type:', type);
          break;
        }
      }

      if (!mimeType) {
        console.log('No specific MIME type supported, letting browser choose');
      }

      // Create MediaRecorder without mimeType if none supported (let browser choose)
      const mediaRecorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      console.log('MediaRecorder created with mimeType:', mediaRecorder.mimeType);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        // Use the mimeType from the MediaRecorder if available
        const blobType = mediaRecorder.mimeType || mimeType || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type: blobType });

        // Create URL for preview
        const url = URL.createObjectURL(blob);
        setAudioBlob(blob);
        setAudioUrl(url);

        // DO NOT stop stream tracks here - keep stream alive for subsequent recordings
        // This prevents iOS from requiring permission again on next recording
        // Stream will be stopped only on component unmount

        // Change state to preview
        setRecordingState('preview');
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }
      };

      mediaRecorder.start();
      setRecordingState('recording');

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);

    } catch (error: any) {
      console.error('Error accessing microphone:', error);

      // Check for iOS-specific "No AVAudioSessionCaptureDevice" error
      const errorMsg = error.message || '';
      if (errorMsg.includes('AVAudioSessionCaptureDevice')) {
        alert('iOS Safari microphone bug detected.\n\nQuick fix:\n1. Close this tab completely\n2. Wait 3 seconds\n3. Open ChatPop in a new tab\n\nIf that doesn\'t work:\n• Close all other tabs/apps\n• Restart Safari\n• Check Settings → Safari → Microphone');
        return;
      }

      // Provide specific error messages based on the error type
      if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        alert('Microphone permission denied.\n\nPlease:\n1. Tap "Allow" when iOS asks for microphone access\n2. Check Settings → Safari → Microphone is set to "Ask" or "Allow"\n3. Reload the page and try again');
      } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        alert('No microphone found. Please connect a microphone and try again.');
      } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
        alert('Microphone is already in use by another application. Please close other apps using the microphone and try again.');
      } else if (error.name === 'TypeError') {
        alert('Voice recording is not supported in your browser. Please try a different browser.');
      } else {
        alert(`Could not access microphone: ${error.message || error.name || 'Unknown error'}`);
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
