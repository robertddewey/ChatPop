'use client';

import { X, Music, Mic, Square } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api';

interface AudioRecognitionResult {
  success: boolean;
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
  error?: string;
}

interface AudioRecordingModalProps {
  onClose: () => void;
}

export default function AudioRecordingModal({ onClose }: AudioRecordingModalProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<AudioRecognitionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const MAX_RECORDING_TIME = 15; // 15 seconds max

  // Cleanup on unmount
  useEffect(() => {
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = 'unset';
      stopRecording();
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    };
  }, []);

  const startRecording = async () => {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

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
        stream.getTracks().forEach(track => track.stop());

        // Create audio blob
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        console.log('🎵 Recording complete:', audioBlob.size, 'bytes');

        // Analyze audio
        await analyzeAudio(audioBlob);
      };

      // Start recording
      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      setError(null);
      setResult(null);

      // Start timer
      timerIntervalRef.current = setInterval(() => {
        setRecordingTime((prev) => {
          const newTime = prev + 1;
          // Auto-stop at max time
          if (newTime >= MAX_RECORDING_TIME) {
            stopRecording();
          }
          return newTime;
        });
      }, 1000);

    } catch (err: any) {
      console.error('❌ Microphone access denied:', err);
      setError('Microphone access denied. Please allow microphone access and try again.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    setIsRecording(false);
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

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getConfidenceColor = (score?: number): string => {
    if (!score) return 'text-gray-400';
    if (score >= 80) return 'text-green-400';
    if (score >= 60) return 'text-yellow-400';
    return 'text-orange-400';
  };

  const getConfidenceLabel = (score?: number): string => {
    if (!score) return 'Unknown';
    if (score >= 90) return 'Very High';
    if (score >= 80) return 'High';
    if (score >= 60) return 'Medium';
    return 'Low';
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
              {isRecording ? 'Recording Audio...' : isAnalyzing ? 'Identifying Song...' : result ? 'Song Found!' : 'Start a music chat'}
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              {isRecording ? '🎤 Listening to audio' : isAnalyzing ? '🔍 Searching music database' : result ? '✨ Recognition complete' : 'Tap record to identify music'}
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
              {/* Timer Display */}
              {isRecording && (
                <div className="text-center">
                  <div className="text-5xl font-mono font-bold text-cyan-400 mb-2">
                    {formatTime(recordingTime)}
                  </div>
                  <div className="text-sm text-zinc-400">
                    Max: {formatTime(MAX_RECORDING_TIME)}
                  </div>
                </div>
              )}

              {/* Record/Stop Button */}
              <button
                onClick={isRecording ? stopRecording : startRecording}
                className={`w-24 h-24 rounded-full flex items-center justify-center transition-all transform hover:scale-105 shadow-xl ${
                  isRecording
                    ? 'bg-red-500 hover:bg-red-600 text-white animate-pulse'
                    : 'bg-cyan-500 hover:bg-cyan-600 text-white'
                }`}
              >
                {isRecording ? (
                  <Square className="w-10 h-10" />
                ) : (
                  <Mic className="w-10 h-10" />
                )}
              </button>

              <p className="text-zinc-300 text-center max-w-sm">
                {isRecording
                  ? 'Recording... Tap to stop and analyze'
                  : 'Tap the microphone to start recording music'}
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
              <div className="p-6 bg-gradient-to-br from-cyan-500/10 to-purple-500/10 border border-cyan-500/30 rounded-xl">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-cyan-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Music className="w-6 h-6 text-cyan-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-xl font-bold text-zinc-50 mb-1 truncate">
                      {result.song}
                    </h3>
                    <p className="text-zinc-300 text-sm truncate">{result.artist}</p>
                    {result.album && (
                      <p className="text-zinc-400 text-xs mt-1 truncate">Album: {result.album}</p>
                    )}
                    {result.release_date && (
                      <p className="text-zinc-400 text-xs">Released: {result.release_date}</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Confidence Score */}
              {result.score !== undefined && (
                <div className="p-4 bg-zinc-900/50 border border-zinc-600 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-zinc-400 text-sm">Confidence</span>
                    <span className={`text-sm font-bold ${getConfidenceColor(result.score)}`}>
                      {getConfidenceLabel(result.score)} ({result.score}%)
                    </span>
                  </div>
                  <div className="w-full bg-zinc-700 rounded-full h-2">
                    <div
                      className="bg-gradient-to-r from-cyan-400 to-purple-400 h-2 rounded-full transition-all"
                      style={{ width: `${result.score}%` }}
                    ></div>
                  </div>
                </div>
              )}

              {/* External Links */}
              {(result.external_ids?.spotify || result.external_ids?.youtube) && (
                <div className="space-y-2">
                  <p className="text-zinc-400 text-sm font-medium">Listen on:</p>
                  <div className="flex gap-2">
                    {result.external_ids.spotify && (
                      <a
                        href={`https://open.spotify.com/track/${result.external_ids.spotify}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-1 px-4 py-3 bg-green-500/10 border border-green-500/30 rounded-lg hover:bg-green-500/20 transition-colors text-center"
                      >
                        <span className="text-green-400 font-medium text-sm">Spotify</span>
                      </a>
                    )}
                    {result.external_ids.youtube && (
                      <a
                        href={`https://www.youtube.com/watch?v=${result.external_ids.youtube}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-1 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg hover:bg-red-500/20 transition-colors text-center"
                      >
                        <span className="text-red-400 font-medium text-sm">YouTube</span>
                      </a>
                    )}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-2 pt-4">
                <button
                  onClick={() => {
                    setResult(null);
                    setError(null);
                  }}
                  className="flex-1 px-4 py-3 bg-zinc-700 hover:bg-zinc-600 text-zinc-100 rounded-lg font-medium transition-colors"
                >
                  Record Again
                </button>
                <button
                  onClick={onClose}
                  className="flex-1 px-4 py-3 bg-cyan-500 hover:bg-cyan-600 text-white rounded-lg font-medium transition-colors"
                >
                  Done
                </button>
              </div>
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
      </div>
    </div>
  );
}
