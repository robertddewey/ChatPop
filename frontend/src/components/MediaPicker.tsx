'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Camera, Video, X, Play, Pause } from 'lucide-react';

interface MediaPickerProps {
  onPhotoSelected?: (file: File, width: number, height: number) => void;
  onVideoSelected?: (file: File, duration: number, thumbnail: Blob | null) => void;
  onMediaReady?: (hasMedia: boolean) => void;
  photoEnabled?: boolean;
  videoEnabled?: boolean;
  disabled?: boolean;
  maxVideoDuration?: number; // in seconds, default 30
  className?: string;
}

type MediaState = 'idle' | 'photo_preview' | 'video_preview';

export default function MediaPicker({
  onPhotoSelected,
  onVideoSelected,
  onMediaReady,
  photoEnabled = true,
  videoEnabled = true,
  disabled = false,
  maxVideoDuration = 30,
  className,
}: MediaPickerProps) {
  const [mediaState, setMediaState] = useState<MediaState>('idle');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [photoDimensions, setPhotoDimensions] = useState<{ width: number; height: number } | null>(null);
  const [videoDuration, setVideoDuration] = useState<number | null>(null);
  const [videoThumbnail, setVideoThumbnail] = useState<Blob | null>(null);
  const [isVideoPlaying, setIsVideoPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const photoInputRef = useRef<HTMLInputElement>(null);
  const videoInputRef = useRef<HTMLInputElement>(null);
  const videoPreviewRef = useRef<HTMLVideoElement>(null);

  // Cleanup preview URLs on unmount
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  // Notify parent when media selection changes
  useEffect(() => {
    if (onMediaReady) {
      onMediaReady(mediaState !== 'idle' && selectedFile !== null);
    }
  }, [mediaState, selectedFile, onMediaReady]);

  const handlePhotoSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setError('Please select an image file');
      return;
    }

    // Validate file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      setError('Photo must be less than 10MB');
      return;
    }

    setError(null);

    // Get image dimensions
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);

    img.onload = () => {
      setPhotoDimensions({ width: img.width, height: img.height });
      setPreviewUrl(objectUrl);
      setSelectedFile(file);
      setMediaState('photo_preview');
    };

    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      setError('Failed to load image');
    };

    img.src = objectUrl;

    // Reset input so same file can be selected again
    if (photoInputRef.current) {
      photoInputRef.current.value = '';
    }
  };

  const handleVideoSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('video/')) {
      setError('Please select a video file');
      return;
    }

    // Validate file size (50MB max)
    if (file.size > 50 * 1024 * 1024) {
      setError('Video must be less than 50MB');
      return;
    }

    setError(null);

    // Get video duration and generate thumbnail
    const video = document.createElement('video');
    const objectUrl = URL.createObjectURL(file);

    video.onloadedmetadata = () => {
      // Check duration
      if (video.duration > maxVideoDuration) {
        URL.revokeObjectURL(objectUrl);
        setError(`Video must be ${maxVideoDuration} seconds or less`);
        return;
      }

      setVideoDuration(video.duration);

      // Generate thumbnail from first frame
      video.currentTime = 0;
    };

    video.onseeked = () => {
      // Create canvas and draw video frame
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');

      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(
          (blob) => {
            if (blob) {
              setVideoThumbnail(blob);
            }
            setPreviewUrl(objectUrl);
            setSelectedFile(file);
            setMediaState('video_preview');
          },
          'image/jpeg',
          0.8
        );
      } else {
        setPreviewUrl(objectUrl);
        setSelectedFile(file);
        setMediaState('video_preview');
      }
    };

    video.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      setError('Failed to load video');
    };

    video.src = objectUrl;

    // Reset input so same file can be selected again
    if (videoInputRef.current) {
      videoInputRef.current.value = '';
    }
  };

  const clearSelection = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setSelectedFile(null);
    setPhotoDimensions(null);
    setVideoDuration(null);
    setVideoThumbnail(null);
    setIsVideoPlaying(false);
    setMediaState('idle');
    setError(null);
  };

  const toggleVideoPlayback = () => {
    if (!videoPreviewRef.current) return;

    if (isVideoPlaying) {
      videoPreviewRef.current.pause();
    } else {
      videoPreviewRef.current.play();
    }
    setIsVideoPlaying(!isVideoPlaying);
  };

  // Use refs to store latest callbacks to avoid stale closures
  const onPhotoSelectedRef = useRef(onPhotoSelected);
  const onVideoSelectedRef = useRef(onVideoSelected);

  useEffect(() => {
    onPhotoSelectedRef.current = onPhotoSelected;
    onVideoSelectedRef.current = onVideoSelected;
  }, [onPhotoSelected, onVideoSelected]);

  // Expose send method to parent via a method they can call
  useEffect(() => {
    const sendMedia = () => {
      if (!selectedFile) return;

      if (mediaState === 'photo_preview' && photoDimensions && onPhotoSelectedRef.current) {
        onPhotoSelectedRef.current(selectedFile, photoDimensions.width, photoDimensions.height);
        clearSelection();
      } else if (mediaState === 'video_preview' && videoDuration !== null && onVideoSelectedRef.current) {
        // Thumbnail is optional - backend will generate if not provided
        onVideoSelectedRef.current(selectedFile, videoDuration, videoThumbnail || null);
        clearSelection();
      }
    };

    (window as any).__mediaPickerSendMethod = sendMedia;
    (window as any).__mediaPickerHasMedia = mediaState !== 'idle' && selectedFile !== null;
    return () => {
      delete (window as any).__mediaPickerSendMethod;
      delete (window as any).__mediaPickerHasMedia;
    };
  }, [selectedFile, mediaState, photoDimensions, videoDuration, videoThumbnail]);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {/* Hidden file inputs */}
      <input
        ref={photoInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handlePhotoSelect}
        className="hidden"
      />
      <input
        ref={videoInputRef}
        type="file"
        accept="video/*"
        capture="environment"
        onChange={handleVideoSelect}
        className="hidden"
      />

      {/* Idle state - show buttons */}
      {mediaState === 'idle' && (
        <>
          {photoEnabled && (
            <button
              type="button"
              onClick={() => photoInputRef.current?.click()}
              disabled={disabled}
              className="p-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              title="Take or select photo"
            >
              <Camera size={20} />
            </button>
          )}
          {videoEnabled && (
            <button
              type="button"
              onClick={() => videoInputRef.current?.click()}
              disabled={disabled}
              className="p-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              title="Record or select video"
            >
              <Video size={20} />
            </button>
          )}
        </>
      )}

      {/* Photo preview state */}
      {mediaState === 'photo_preview' && previewUrl && (
        <div className="flex items-center gap-2">
          <div className="relative w-12 h-12 rounded-lg overflow-hidden bg-gray-200 dark:bg-zinc-700">
            <img
              src={previewUrl}
              alt="Photo preview"
              className="w-full h-full object-cover"
            />
          </div>
          <button
            type="button"
            onClick={clearSelection}
            className="p-2 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
            title="Remove photo"
          >
            <X size={18} />
          </button>
        </div>
      )}

      {/* Video preview state */}
      {mediaState === 'video_preview' && previewUrl && (
        <div className="flex items-center gap-2">
          <div className="relative w-12 h-12 rounded-lg overflow-hidden bg-gray-200 dark:bg-zinc-700">
            <video
              ref={videoPreviewRef}
              src={previewUrl}
              className="w-full h-full object-cover"
              muted
              playsInline
              onEnded={() => setIsVideoPlaying(false)}
            />
            <button
              type="button"
              onClick={toggleVideoPlayback}
              className="absolute inset-0 flex items-center justify-center bg-black/30"
            >
              {isVideoPlaying ? (
                <Pause size={16} className="text-white" />
              ) : (
                <Play size={16} className="text-white" fill="white" />
              )}
            </button>
          </div>
          <button
            type="button"
            onClick={clearSelection}
            className="p-2 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
            title="Remove video"
          >
            <X size={18} />
          </button>
        </div>
      )}

      {/* Error display */}
      {error && (
        <span className="text-xs text-red-500">{error}</span>
      )}
    </div>
  );
}
