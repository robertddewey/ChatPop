'use client';

import { useState, useEffect } from 'react';
import { X, Camera, RefreshCw } from 'lucide-react';
import { devApi, DevRecentPhoto } from '@/lib/api';
import { getModalTheme } from '@/lib/modal-theme';

interface DevPhotoPickerProps {
  onSelect: (file: File) => void;
  onClose: () => void;
}

export default function DevPhotoPicker({ onSelect, onClose }: DevPhotoPickerProps) {
  const [photos, setPhotos] = useState<DevRecentPhoto[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch recent photos from backend on mount
  useEffect(() => {
    const fetchPhotos = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const recentPhotos = await devApi.getRecentPhotos();
        setPhotos(recentPhotos);
      } catch (err) {
        console.error('[DevPhotoPicker] Failed to fetch photos:', err);
        setError('Failed to load recent photos');
      } finally {
        setIsLoading(false);
      }
    };

    fetchPhotos();
  }, []);

  const handlePhotoSelect = async (photo: DevRecentPhoto) => {
    setSelectedId(photo.id);

    try {
      // Fetch the actual image file from the backend
      const response = await fetch(photo.image_url);
      if (!response.ok) {
        throw new Error('Failed to fetch photo');
      }

      const blob = await response.blob();
      // Extract filename from URL or use a default
      const urlParts = photo.image_url.split('/');
      const filename = urlParts[urlParts.length - 1] || 'photo.jpg';
      const file = new File([blob], filename, { type: blob.type || 'image/jpeg' });

      console.log('📸 [DEV] Selected photo from backend:', filename);
      onSelect(file);
    } catch (err) {
      console.error('[DevPhotoPicker] Failed to get photo file:', err);
      setSelectedId(null);
      setError('Failed to load selected photo');
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

  const handleRefresh = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const recentPhotos = await devApi.getRecentPhotos();
      setPhotos(recentPhotos);
    } catch (err) {
      console.error('[DevPhotoPicker] Failed to refresh photos:', err);
      setError('Failed to refresh photos');
    } finally {
      setIsLoading(false);
    }
  };

  const mt = getModalTheme(true);

  return (
    <div className={`fixed inset-0 z-[60] flex items-center justify-center p-4 ${mt.backdrop}`}>
      <div className={`w-full max-w-md ${mt.container} ${mt.border} ${mt.rounded} ${mt.shadow} relative max-h-[85dvh] overflow-hidden flex flex-col`}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-700">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-amber-500/20 rounded-lg flex items-center justify-center">
              <Camera className="w-4 h-4 text-amber-400" />
            </div>
            <div>
              <h2 className={`text-lg font-bold ${mt.title}`}>Dev: Recent Photos</h2>
              <p className={`text-xs ${mt.body}`}>Select a photo to re-analyze</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={isLoading || selectedId !== null}
              className={`p-2 rounded-lg transition-colors disabled:opacity-50 ${mt.closeButton}`}
            >
              <RefreshCw className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className={`p-2 rounded-lg transition-colors ${mt.closeButton}`}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-8 h-8 border-2 border-zinc-600 border-t-amber-400 rounded-full animate-spin" />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mb-4">
                <Camera className="w-8 h-8 text-red-400" />
              </div>
              <p className="text-red-400 mb-2">{error}</p>
              <button
                onClick={handleRefresh}
                className="text-amber-400 text-sm hover:underline"
              >
                Try again
              </button>
            </div>
          ) : photos.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-16 h-16 bg-zinc-700 rounded-full flex items-center justify-center mb-4">
                <Camera className="w-8 h-8 text-zinc-500" />
              </div>
              <p className="text-zinc-400 mb-2">No photos yet</p>
              <p className="text-zinc-500 text-sm">
                Upload a photo using the camera or library button first
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2">
              {photos.map((photo) => (
                <button
                  key={photo.id}
                  onClick={() => handlePhotoSelect(photo)}
                  disabled={selectedId !== null}
                  className={`relative aspect-square rounded-lg overflow-hidden border-2 transition-all ${
                    selectedId === photo.id
                      ? 'border-amber-400 ring-2 ring-amber-400/50'
                      : selectedId !== null
                      ? 'border-zinc-700 opacity-50'
                      : 'border-zinc-700 hover:border-amber-400/50'
                  }`}
                >
                  <img
                    src={photo.image_url}
                    alt="Recent photo"
                    className="w-full h-full object-cover"
                  />
                  {selectedId === photo.id && (
                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                      <div className="w-6 h-6 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
                    </div>
                  )}
                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-1">
                    <p className="text-[10px] text-zinc-300 truncate">{formatDate(photo.created_at)}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-700 flex gap-2">
          <button
            onClick={onClose}
            disabled={selectedId !== null}
            className={`flex-1 px-4 py-2 rounded-lg transition-colors disabled:opacity-50 ${mt.secondaryButton}`}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
