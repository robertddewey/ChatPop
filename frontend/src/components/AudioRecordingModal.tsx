'use client';

import { X, Music, Mic } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api';

interface MusicSuggestion {
  name: string;
  key: string;
  type: 'artist' | 'song' | 'genre';
}

interface AudioRecognitionResult {
  success: boolean;
  id?: string;
  song: string;
  artist: string;
  album?: string;
  release_date?: string;
  duration_ms?: number;
  score?: number;
  external_ids?: {
    spotify?: string;
    youtube?: string;
  };
  suggestions?: MusicSuggestion[];
  error?: string;
}

interface AudioRecordingModalProps {
  onClose: () => void;
}

const DEFAULT_RECORDING_DURATION = 8; // Fallback if config fetch fails

export default function AudioRecordingModal({ onClose }: AudioRecordingModalProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<AudioRecognitionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recordingDuration, setRecordingDuration] = useState(DEFAULT_RECORDING_DURATION);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const autoStopTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Fetch config and cleanup on unmount
  useEffect(() => {
    document.body.style.overflow = 'hidden';

    // Fetch recording duration from backend config
    const fetchConfig = async () => {
      try {
        const response = await api.get('/api/media-analysis/music/config/');
        if (response.data?.recording_duration_seconds) {
          setRecordingDuration(response.data.recording_duration_seconds);
        }
      } catch (err) {
        console.warn('Failed to fetch music config, using default duration:', DEFAULT_RECORDING_DURATION);
      }
    };
    fetchConfig();

    return () => {
      document.body.style.overflow = 'unset';
      cleanupRecording();
    };
  }, []);

  const cleanupRecording = () => {
    // Stop media recorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    // Stop all audio tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    // Clear auto-stop timeout
    if (autoStopTimeoutRef.current) {
      clearTimeout(autoStopTimeoutRef.current);
      autoStopTimeoutRef.current = null;
    }
    setIsRecording(false);
  };

  const startRecording = async () => {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Create MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });

      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      // Collect audio data
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      // Handle recording stop
      mediaRecorder.onstop = async () => {
        // Stop all audio tracks
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }

        // Create audio blob
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        console.log('🎵 Recording complete:', audioBlob.size, 'bytes');

        // Analyze audio
        await analyzeAudio(audioBlob);
      };

      // Start recording
      mediaRecorder.start();
      setIsRecording(true);
      setError(null);
      setResult(null);

      // Auto-stop after configured duration
      autoStopTimeoutRef.current = setTimeout(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
          console.log(`🎵 Auto-stopping recording after ${recordingDuration} seconds`);
          mediaRecorderRef.current.stop();
          setIsRecording(false);
        }
      }, recordingDuration * 1000);

    } catch (err: any) {
      console.error('❌ Microphone access denied:', err);
      setError('Microphone access denied. Please allow microphone access and try again.');
    }
  };

  const analyzeAudio = async (audioBlob: Blob) => {
    setIsAnalyzing(true);
    setError(null);

    try {
      // Prepare form data
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');

      // Send to backend
      const response = await api.post('/api/media-analysis/music/recognize/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      console.log('✅ Song recognized:', response.data);
      setResult(response.data);

    } catch (err: any) {
      console.error('❌ Audio recognition failed:', err.response?.data || err.message);
      const errorMessage = err.response?.data?.error || err.response?.data?.detail || 'Recognition failed';
      setError(errorMessage);
      setResult(null);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getSuggestionDescription = (suggestion: MusicSuggestion, result: AudioRecognitionResult): string => {
    if (suggestion.type === 'artist') {
      return `Chat about music by ${suggestion.name}`;
    } else if (suggestion.type === 'genre') {
      return `Chat about ${suggestion.name.toLowerCase()}`;
    } else {
      // song type
      return `Chat about "${result.song}" by ${result.artist}`;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      {/* Modal Container */}
      <div className="w-full max-w-md bg-zinc-800 border border-zinc-700 rounded-2xl shadow-xl relative max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-700">
          <div>
            <h1 className="text-2xl font-bold text-zinc-50 flex items-center gap-2">
              <Music className="w-6 h-6" />
              {isRecording ? 'Recording Audio...' : isAnalyzing ? 'Identifying Song...' : result?.success ? 'Song Found!' : 'Start a music chat'}
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              {isRecording ? '🎤 Listening to audio' : isAnalyzing ? '🔍 Searching music database' : result?.success ? '✨ Recognition complete' : 'Tap record to identify music'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg transition-colors text-zinc-300 hover:text-zinc-100 hover:bg-zinc-700 cursor-pointer"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 flex-1 overflow-y-auto">
          {/* Recording Controls */}
          {!isAnalyzing && !result && (
            <div className="flex flex-col items-center justify-center space-y-6">
              {/* Record Button */}
              <button
                onClick={startRecording}
                disabled={isRecording}
                className={`w-24 h-24 rounded-full flex items-center justify-center transition-all transform shadow-xl ${
                  isRecording
                    ? 'bg-red-500 text-white animate-pulse cursor-not-allowed'
                    : 'bg-cyan-500 hover:bg-cyan-600 hover:scale-105 text-white cursor-pointer'
                }`}
              >
                <Mic className="w-10 h-10" />
              </button>

              <p className="text-zinc-300 text-center max-w-sm">
                {isRecording
                  ? 'Listening...'
                  : 'Tap the microphone to identify music'}
              </p>

              {error && (
                <div className="w-full p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              )}
            </div>
          )}

          {/* Analyzing State */}
          {isAnalyzing && (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              <div className="w-16 h-16 border-4 border-zinc-600 border-t-cyan-400 rounded-full animate-spin"></div>
              <p className="text-zinc-300 text-lg font-medium">Identifying song...</p>
              <p className="text-zinc-500 text-sm">Searching music database</p>
            </div>
          )}

          {/* Results State */}
          {result && result.success && (
            <div className="space-y-4">
              {/* Song Info Card */}
              <div className="p-4 bg-zinc-900/50 border border-zinc-600 rounded-lg">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 bg-cyan-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Music className="w-5 h-5 text-cyan-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-bold text-zinc-50 truncate">
                      {result.song}
                    </h3>
                    <p className="text-zinc-300 text-sm truncate">{result.artist}</p>
                  </div>
                </div>
              </div>

              {/* Suggestions */}
              {result.suggestions && result.suggestions.length > 0 && (
                <div>
                  <h2 className="text-lg font-bold text-zinc-200 mb-3">
                    Suggested Chat Rooms ({result.suggestions.length})
                  </h2>
                  <div className="space-y-3">
                    {result.suggestions.map((suggestion, idx) => (
                      <div
                        key={suggestion.key}
                        className="p-4 bg-zinc-900/50 border border-zinc-600 rounded-lg hover:border-cyan-400 transition-colors cursor-pointer"
                      >
                        {/* Name and Badge */}
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-zinc-400">#{idx + 1}</span>
                            <h3 className="text-base font-bold text-zinc-50">{suggestion.name}</h3>
                            <span className="px-2 py-0.5 bg-purple-900/40 border border-purple-700 text-purple-300 text-xs font-semibold rounded uppercase">
                              {suggestion.type}
                            </span>
                          </div>
                        </div>

                        {/* Description */}
                        <p className="text-sm text-zinc-300">{getSuggestionDescription(suggestion, result)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Error in Result */}
          {result && !result.success && result.error && (
            <div className="space-y-4">
              <div className="p-6 bg-red-500/10 border border-red-500/30 rounded-xl text-center">
                <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <X className="w-8 h-8 text-red-400" />
                </div>
                <h3 className="text-lg font-bold text-red-400 mb-2">No Match Found</h3>
                <p className="text-zinc-400 text-sm">{result.error}</p>
              </div>

              <button
                onClick={() => {
                  setResult(null);
                  setError(null);
                }}
                className="w-full px-4 py-3 bg-zinc-700 hover:bg-zinc-600 text-zinc-100 rounded-lg font-medium transition-colors"
              >
                Try Again
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-700">
          <button
            onClick={onClose}
            className="w-full px-6 py-3 bg-[#404eed] text-white font-semibold rounded-lg transition-all hover:bg-[#3640d9] cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
