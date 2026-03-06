'use client';

import { useState, useEffect } from 'react';
import { X, Music, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { getModalTheme } from '@/lib/modal-theme';

interface RecentSong {
  id: string;
  song: string;
  artist: string;
  album: string;
  created_at: string;
}

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
  genres?: string[];
  suggestions?: MusicSuggestion[];
  error?: string;
}

interface DevMusicPickerProps {
  onSelect: (result: AudioRecognitionResult) => void;
  onClose: () => void;
}

export default function DevMusicPicker({ onSelect, onClose }: DevMusicPickerProps) {
  const [songs, setSongs] = useState<RecentSong[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Fetch recent songs on mount
  useEffect(() => {
    const fetchRecentSongs = async () => {
      try {
        const response = await api.get('/api/media-analysis/music/dev/recent-songs/');
        setSongs(response.data);
      } catch (err: unknown) {
        const error = err as { response?: { data?: { error?: string } } };
        console.error('Failed to fetch recent songs:', err);
        setError(error.response?.data?.error || 'Failed to load recent songs');
      } finally {
        setIsLoading(false);
      }
    };

    fetchRecentSongs();
  }, []);

  const handleSongSelect = async (song: RecentSong) => {
    setSelectedId(song.id);
    setError(null);

    try {
      // Fetch the full analysis using the replay endpoint
      const response = await api.get(`/api/media-analysis/music/${song.id}/dev/replay/`);
      console.log('🎵 [DEV] Replaying music analysis:', response.data);
      onSelect(response.data);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { error?: string } } };
      console.error('Failed to replay music analysis:', err);
      setError(error.response?.data?.error || 'Failed to load song analysis');
      setSelectedId(null);
    }
  };

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const mt = getModalTheme(true);

  return (
    <div className={`fixed inset-0 z-[60] flex items-center justify-center p-4 ${mt.backdrop}`}>
      <div className={`w-full max-w-md ${mt.container} ${mt.border} ${mt.rounded} ${mt.shadow} overflow-hidden flex flex-col max-h-[85dvh]`}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-700 bg-amber-900/30">
          <div className="flex items-center gap-2">
            <div className="px-2 py-1 bg-amber-500 text-black text-xs font-bold rounded">DEV</div>
            <h2 className={`text-lg font-bold ${mt.title}`}>Select Recent Song</h2>
          </div>
          <button
            onClick={onClose}
            className={`p-2 rounded-lg cursor-pointer ${mt.closeButton}`}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              <div className="w-8 h-8 border-2 border-zinc-600 border-t-cyan-400 rounded-full animate-spin" />
              <p className="text-zinc-400 text-sm">Loading recent songs...</p>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg mb-4">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          {!isLoading && songs.length === 0 && !error && (
            <div className="text-center py-12">
              <Music className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <p className="text-zinc-400">No recent songs found</p>
              <p className="text-zinc-500 text-sm mt-1">Record some music first!</p>
            </div>
          )}

          {!isLoading && songs.length > 0 && (
            <div className="space-y-2">
              {songs.map((song) => (
                <button
                  key={song.id}
                  onClick={() => handleSongSelect(song)}
                  disabled={selectedId !== null}
                  className={`w-full text-left p-4 rounded-lg border transition-all ${
                    selectedId === song.id
                      ? 'bg-cyan-900/30 border-cyan-500'
                      : selectedId !== null
                      ? 'bg-zinc-900/50 border-zinc-700 opacity-50 cursor-not-allowed'
                      : 'bg-zinc-900/50 border-zinc-700 hover:border-cyan-500 cursor-pointer'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 bg-cyan-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                      {selectedId === song.id ? (
                        <Loader2 className="w-5 h-5 text-cyan-400 animate-spin" />
                      ) : (
                        <Music className="w-5 h-5 text-cyan-400" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-base font-bold text-zinc-50 truncate">{song.song}</h3>
                      <p className="text-zinc-400 text-sm truncate">{song.artist}</p>
                      <p className="text-zinc-500 text-xs mt-1">{formatDate(song.created_at)}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-700">
          <button
            onClick={onClose}
            disabled={selectedId !== null}
            className={`w-full px-4 py-3 font-semibold rounded-lg transition-colors ${mt.secondaryButton} ${
              selectedId !== null ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
            }`}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
