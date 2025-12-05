'use client';

import { X } from 'lucide-react';
import { useEffect } from 'react';

interface Suggestion {
  id: number;
  name: string;
  key: string;
  description: string;
  source: string;
  usage_count: number;
  has_room: boolean;
  active_users: number;
  is_proper_noun: boolean;
}

interface Analysis {
  id: number;
  suggestions: Suggestion[];
}

interface PhotoAnalysisResult {
  cached: boolean;
  analysis: Analysis;
}

interface PhotoAnalysisModalProps {
  result: PhotoAnalysisResult | null;
  isLoading: boolean;
  onClose: () => void;
}

export default function PhotoAnalysisModal({ result, isLoading, onClose }: PhotoAnalysisModalProps) {
  // Prevent body scrolling when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      {/* Modal Container */}
      <div className="w-full max-w-2xl bg-zinc-800 border border-zinc-700 rounded-2xl shadow-xl relative max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-700">
          <div>
            <h1 className="text-2xl font-bold text-zinc-50">
              {isLoading ? 'Analyzing Photo...' : 'Photo Analysis Complete'}
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              {isLoading ? '🔍 Processing your image' : (result?.cached ? '📊 Cached result' : '✨ Fresh analysis')}
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
              {/* Analysis ID */}
              <div className="mb-4 p-3 bg-zinc-900/50 border border-zinc-600 rounded-lg">
                <p className="text-xs text-zinc-400 uppercase tracking-wide mb-1">Analysis ID</p>
                <p className="text-sm text-zinc-200 font-mono">{result.analysis.id}</p>
              </div>

              {/* Suggestions */}
              <div>
                <h2 className="text-lg font-bold text-zinc-200 mb-3">
                  Suggested Chat Rooms ({result.analysis.suggestions.length})
                </h2>

                {result.analysis.suggestions.length === 0 ? (
                  <p className="text-zinc-400 text-center py-8">No suggestions found for this photo.</p>
                ) : (
                  <div className="space-y-3">
                    {result.analysis.suggestions.map((suggestion, idx) => (
                      <div
                        key={suggestion.id}
                        className="p-4 bg-zinc-900/50 border border-zinc-600 rounded-lg hover:border-cyan-400 transition-colors"
                      >
                        {/* Name and Badge */}
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-zinc-400">#{idx + 1}</span>
                            <h3 className="text-base font-bold text-zinc-50">{suggestion.name}</h3>
                            {suggestion.is_proper_noun && (
                              <span className="px-2 py-0.5 bg-purple-900/40 border border-purple-700 text-purple-300 text-xs font-semibold rounded">
                                PROPER NOUN
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Description */}
                        <p className="text-sm text-zinc-300 mb-3">{suggestion.description}</p>

                        {/* Stats Grid */}
                        <div className="grid grid-cols-2 gap-3 text-xs">
                          <div className="flex items-center gap-1.5">
                            <span className="text-zinc-500">Source:</span>
                            <span className="text-zinc-300 font-medium">{suggestion.source}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="text-zinc-500">Usage:</span>
                            <span className="text-zinc-300 font-medium">{suggestion.usage_count}x</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="text-zinc-500">Has Room:</span>
                            <span className="text-zinc-300 font-medium">
                              {suggestion.has_room ? 'Yes' : 'No'}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="text-zinc-500">Active Users:</span>
                            <span className="text-zinc-300 font-medium">{suggestion.active_users}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-700">
          <button
            onClick={onClose}
            disabled={isLoading}
            className={`w-full px-6 py-3 bg-[#404eed] text-white font-semibold rounded-lg transition-all ${
              isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:bg-[#3640d9] cursor-pointer'
            }`}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
