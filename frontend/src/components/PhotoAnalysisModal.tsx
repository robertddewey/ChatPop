'use client';

import { X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { messageApi } from '@/lib/api';

import type { PhotoAnalysisResponse, PhotoSuggestion } from '@/lib/api';

type PhotoAnalysisResult = PhotoAnalysisResponse;

interface PhotoAnalysisModalProps {
  result: PhotoAnalysisResult | null;
  isLoading: boolean;
  onClose: () => void;
}

export default function PhotoAnalysisModal({ result, isLoading, onClose }: PhotoAnalysisModalProps) {
  const router = useRouter();
  const [selectingIndex, setSelectingIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Prevent body scrolling when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  const handleSuggestionClick = async (suggestion: PhotoSuggestion, index: number) => {
    if (!result || selectingIndex !== null) return;

    setSelectingIndex(index);
    setError(null);

    try {
      // Create or join the room
      const response = await messageApi.createChatFromPhoto({
        media_analysis_id: result.analysis.id.toString(),
        room_code: suggestion.key,
      });

      console.log('Room created/joined:', response);

      // Navigate to the room
      // URL will be /chat/discover/{key} for AI rooms
      router.push(response.chat_room.url);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      console.error('Failed to create/join room:', err);
      setError(error.response?.data?.detail || error.message || 'Failed to join room');
      setSelectingIndex(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      {/* Modal Container */}
      <div className="w-full max-w-2xl bg-zinc-800 border border-zinc-700 rounded-2xl shadow-xl relative max-h-[85dvh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-700">
          <div>
            <h1 className="text-2xl font-bold text-zinc-50">
              {isLoading ? 'Analyzing Photo...' : 'Join a Chat'}
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              {isLoading ? 'Finding relevant chat rooms' : `${result?.analysis.suggestions.length || 0} rooms found`}
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

        {/* Content - Scrollable */}
        <div className="overflow-y-auto p-6 flex-1">
          {isLoading ? (
            /* Loading State */
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              {/* Spinning Loader */}
              <div className="w-16 h-16 border-4 border-zinc-600 border-t-cyan-400 rounded-full animate-spin"></div>
              <p className="text-zinc-300 text-lg font-medium">Generating results...</p>
              <p className="text-zinc-500 text-sm">This may take a few moments</p>
            </div>
          ) : result ? (
            /* Results State */
            <>
              {/* Suggestions */}
              <div>
                <h2 className="text-lg font-bold text-zinc-200 mb-3">
                  Suggested Rooms
                </h2>

                {result.analysis.suggestions.length === 0 ? (
                  <p className="text-zinc-400 text-center py-8">No suggestions found for this photo.</p>
                ) : (
                  <div className="space-y-3">
                    {result.analysis.suggestions.map((suggestion, idx) => {
                      const isSelecting = selectingIndex === idx;
                      const isDisabled = selectingIndex !== null && selectingIndex !== idx;

                      return (
                        <button
                          key={suggestion.key}
                          onClick={() => handleSuggestionClick(suggestion, idx)}
                          disabled={selectingIndex !== null}
                          className={`w-full text-left p-4 bg-zinc-900/50 border rounded-lg transition-all ${
                            isSelecting
                              ? 'border-cyan-400 bg-cyan-900/20'
                              : isDisabled
                              ? 'border-zinc-700 opacity-50 cursor-not-allowed'
                              : 'border-zinc-600 hover:border-cyan-400 hover:bg-zinc-800/50 cursor-pointer'
                          }`}
                        >
                          {/* Name Row */}
                          <div className="flex items-start justify-between mb-1">
                            <h3 className="text-base font-bold text-zinc-50">{suggestion.name}</h3>
                            {isSelecting && (
                              <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                            )}
                          </div>

                          {/* Activity Indicator */}
                          <div className="flex items-center gap-2 mb-2">
                            {suggestion.active_users > 0 ? (
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
                          <p className="text-sm text-zinc-300 line-clamp-2">{suggestion.description}</p>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-700">
          {error && (
            <div className="mb-3 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300 text-sm">
              {error}
            </div>
          )}
          {!isLoading && result && (
            <p className="text-center text-zinc-400 text-sm mb-3">
              Tap a suggestion to join the chat room
            </p>
          )}
          <button
            onClick={onClose}
            disabled={isLoading || selectingIndex !== null}
            className={`w-full px-6 py-3 bg-zinc-700 text-white font-semibold rounded-lg transition-all ${
              isLoading || selectingIndex !== null ? 'opacity-50 cursor-not-allowed' : 'hover:bg-zinc-600 cursor-pointer'
            }`}
          >
            {selectingIndex !== null ? 'Joining room...' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  );
}
