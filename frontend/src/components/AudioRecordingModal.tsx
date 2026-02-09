'use client';

import { X, Music, Mic, Loader2 } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { api, messageApi } from '@/lib/api';
import dynamic from 'next/dynamic';

// Only load DevMusicPicker in development mode
const DevMusicPicker = process.env.NODE_ENV === 'development'
  ? dynamic(() => import('./DevMusicPicker'), { ssr: false })
  : null;

interface MusicSuggestion {
  name: string;
  key: string;
  type: 'artist' | 'song' | 'genre';
  active_users?: number;
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
  const router = useRouter();
  const [isRecording, setIsRecording] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<AudioRecognitionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recordingDuration, setRecordingDuration] = useState(DEFAULT_RECORDING_DURATION);

  // Selection state for joining chat rooms
  const [selectingIndex, setSelectingIndex] = useState<number | null>(null);
  const [selectionError, setSelectionError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const autoStopTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Dev mode music picker state (only in development)
  const [showDevPicker, setShowDevPicker] = useState(false);
  const longPressTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isDev = process.env.NODE_ENV === 'development';

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

    } catch (err: unknown) {
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

    } catch (err: unknown) {
      const error = err as { response?: { data?: { error?: string; detail?: string } }; message?: string };
      console.error('❌ Audio recognition failed:', error.response?.data || error.message);
      const errorMessage = error.response?.data?.error || error.response?.data?.detail || 'Recognition failed';
      setError(errorMessage);
      setResult(null);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Dev mode: Handle song selected from picker
  const handleDevSongSelect = (devResult: AudioRecognitionResult) => {
    setShowDevPicker(false);
    setResult(devResult);
  };

  // Long-press handlers for dev mode
  const handleLongPressStart = () => {
    if (!isDev || isRecording) return;

    longPressTimerRef.current = setTimeout(() => {
      console.log('🎵 [DEV] Long press detected - opening music picker');
      setShowDevPicker(true);
    }, 1500); // 1.5 second long press
  };

  const handleLongPressEnd = () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
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

  const handleSuggestionClick = async (suggestion: MusicSuggestion, index: number) => {
    if (!result || !result.id || selectingIndex !== null) return;

    setSelectingIndex(index);
    setSelectionError(null);

    try {
      const response = await messageApi.createChatFromMusic({
        music_analysis_id: result.id,
        room_code: suggestion.key,
      });

      // Navigate to the chat room
      router.push(response.chat_room.url);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      console.error('Failed to join music chat room:', err);
      setSelectionError(error.response?.data?.detail || error.message || 'Failed to join room');
      setSelectingIndex(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      {/* Modal Container */}
      <div className="w-full max-w-md bg-zinc-800 border border-zinc-700 rounded-2xl shadow-xl relative max-h-[85dvh] overflow-hidden flex flex-col">
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
                onMouseDown={handleLongPressStart}
                onMouseUp={handleLongPressEnd}
                onMouseLeave={handleLongPressEnd}
                onTouchStart={handleLongPressStart}
                onTouchEnd={handleLongPressEnd}
                onTouchCancel={handleLongPressEnd}
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

              {/* Selection Error */}
              {selectionError && (
                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg mb-4">
                  <p className="text-red-400 text-sm">{selectionError}</p>
                </div>
              )}

              {/* Suggestions */}
              {result.suggestions && result.suggestions.length > 0 && (
                <div>
                  <h2 className="text-lg font-bold text-zinc-200 mb-3">
                    Suggested Rooms
                  </h2>
                  <div className="space-y-3">
                    {result.suggestions.map((suggestion, idx) => (
                      <div
                        key={suggestion.key}
                        onClick={() => handleSuggestionClick(suggestion, idx)}
                        className={`p-4 bg-zinc-900/50 border rounded-lg transition-colors cursor-pointer ${
                          selectingIndex === idx
                            ? 'border-cyan-400 opacity-70'
                            : selectingIndex !== null
                            ? 'border-zinc-600 opacity-50 cursor-not-allowed'
                            : 'border-zinc-600 hover:border-cyan-400'
                        }`}
                      >
                        {/* Name Row */}
                        <div className="flex items-start justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <h3 className="text-base font-bold text-zinc-50">{suggestion.name}</h3>
                            <span className="px-2 py-0.5 bg-zinc-700 text-zinc-300 text-xs font-medium rounded-full capitalize">
                              {suggestion.type}
                            </span>
                          </div>
                          {selectingIndex === idx && (
                            <Loader2 className="w-5 h-5 text-cyan-400 animate-spin" />
                          )}
                        </div>

                        {/* Activity Indicator */}
                        <div className="flex items-center gap-2 mb-2">
                          {suggestion.active_users && suggestion.active_users > 0 ? (
                            <>
                              <span className="w-2 h-2 rounded-full bg-emerald-400" />
                              <span className="text-xs text-emerald-400 font-medium">
                                {suggestion.active_users} active today
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="w-2 h-2 rounded-full bg-zinc-500" />
                              <span className="text-xs text-zinc-400">
                                Discover this chat
                              </span>
                            </>
                          )}
                        </div>

                        {/* Description */}
                        <p className="text-sm text-zinc-300 line-clamp-2">{getSuggestionDescription(suggestion, result)}</p>
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
          {result?.success && result.suggestions && result.suggestions.length > 0 && (
            <p className="text-center text-zinc-400 text-sm mb-3">
              Tap a suggestion to join the chat room
            </p>
          )}
          <button
            onClick={onClose}
            disabled={selectingIndex !== null}
            className={`w-full px-6 py-3 bg-zinc-700 text-white font-semibold rounded-lg transition-all ${
              selectingIndex !== null ? 'opacity-50 cursor-not-allowed' : 'hover:bg-zinc-600 cursor-pointer'
            }`}
          >
            {selectingIndex !== null ? 'Joining room...' : 'Close'}
          </button>
        </div>
      </div>

      {/* Dev Mode Music Picker */}
      {isDev && DevMusicPicker && showDevPicker && (
        <DevMusicPicker
          onSelect={handleDevSongSelect}
          onClose={() => setShowDevPicker(false)}
        />
      )}
    </div>
  );
}
