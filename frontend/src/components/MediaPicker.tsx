'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Camera, Video } from 'lucide-react';

export interface MediaPreview {
  type: 'photo' | 'video';
  url: string;
  file: File;
  dimensions?: { width: number; height: number };
  duration?: number;
  thumbnailUrl?: string;
}

interface MediaPickerProps {
  onPhotoSelected?: (file: File, width: number, height: number, caption: string) => void;
  onVideoSelected?: (file: File, duration: number, thumbnail: Blob | null, caption: string) => void;
  onMediaReady?: (hasMedia: boolean) => void;
  onSendComplete?: () => void;
  onPreviewChange?: (preview: MediaPreview | null) => void;
  clearRef?: React.MutableRefObject<(() => void) | null>;
  caption?: string;
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
  onSendComplete,
  onPreviewChange,
  clearRef,
  caption = '',
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
  const [videoDimensions, setVideoDimensions] = useState<{ width: number; height: number } | null>(null);
  const [videoThumbnail, setVideoThumbnail] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);

  const photoInputRef = useRef<HTMLInputElement>(null);
  const videoInputRef = useRef<HTMLInputElement>(null);

  // Cleanup preview URLs on unmount
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  // Expose clearSelection to parent via ref
  useEffect(() => {
    if (clearRef) clearRef.current = clearSelection;
  });

  // Notify parent when media selection changes
  useEffect(() => {
    if (onMediaReady) {
      onMediaReady(mediaState !== 'idle' && selectedFile !== null);
    }
  }, [mediaState, selectedFile, onMediaReady]);

  // Create a stable thumbnail URL from the blob
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  useEffect(() => {
    if (videoThumbnail) {
      const url = URL.createObjectURL(videoThumbnail);
      setThumbnailUrl(url);
      return () => URL.revokeObjectURL(url);
    }
    setThumbnailUrl(null);
  }, [videoThumbnail]);

  // Notify parent of preview state changes
  useEffect(() => {
    if (!onPreviewChange) return;
    if (mediaState === 'photo_preview' && previewUrl && selectedFile) {
      onPreviewChange({ type: 'photo', url: previewUrl, file: selectedFile, dimensions: photoDimensions || undefined });
    } else if (mediaState === 'video_preview' && previewUrl && selectedFile) {
      onPreviewChange({ type: 'video', url: previewUrl, file: selectedFile, dimensions: videoDimensions || undefined, duration: videoDuration || undefined, thumbnailUrl: thumbnailUrl || undefined });
    } else {
      onPreviewChange(null);
    }
  }, [mediaState, previewUrl, selectedFile, photoDimensions, videoDimensions, videoDuration, thumbnailUrl, onPreviewChange]);

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
    video.preload = 'auto';
    video.muted = true;
    video.playsInline = true;
    const objectUrl = URL.createObjectURL(file);

    video.onloadedmetadata = () => {
      // Check duration
      if (video.duration > maxVideoDuration) {
        URL.revokeObjectURL(objectUrl);
        setError(`Video must be ${maxVideoDuration} seconds or less`);
        return;
      }

      setVideoDuration(video.duration);
    };

    // Wait until actual frame data is available before seeking
    video.onloadeddata = () => {
      // Seek past potential black first frame
      video.currentTime = Math.min(0.1, video.duration);
    };

    video.onseeked = () => {
      // Capture video dimensions
      setVideoDimensions({ width: video.videoWidth, height: video.videoHeight });

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
    video.load();

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
    setVideoDimensions(null);
    setVideoThumbnail(null);
    setMediaState('idle');
    setError(null);
  };

  // Use refs to store latest callbacks and caption to avoid stale closures
  const onPhotoSelectedRef = useRef(onPhotoSelected);
  const onVideoSelectedRef = useRef(onVideoSelected);
  const onSendCompleteRef = useRef(onSendComplete);
  const captionRef = useRef(caption);

  useEffect(() => {
    onPhotoSelectedRef.current = onPhotoSelected;
    onVideoSelectedRef.current = onVideoSelected;
    onSendCompleteRef.current = onSendComplete;
    captionRef.current = caption;
  }, [onPhotoSelected, onVideoSelected, onSendComplete, caption]);

  // Expose send method to parent via a method they can call
  useEffect(() => {
    const sendMedia = () => {
      if (!selectedFile) return;

      if (mediaState === 'photo_preview' && photoDimensions && onPhotoSelectedRef.current) {
        onPhotoSelectedRef.current(selectedFile, photoDimensions.width, photoDimensions.height, captionRef.current || '');
        onSendCompleteRef.current?.();
        clearSelection();
      } else if (mediaState === 'video_preview' && videoDuration !== null && onVideoSelectedRef.current) {
        // Thumbnail is optional - backend will generate if not provided
        onVideoSelectedRef.current(selectedFile, videoDuration, videoThumbnail || null, captionRef.current || '');
        onSendCompleteRef.current?.();
        clearSelection();
      }
    };

    const win = window as Window & { __mediaPickerSendMethod?: () => void; __mediaPickerHasMedia?: boolean };
    win.__mediaPickerSendMethod = sendMedia;
    win.__mediaPickerHasMedia = mediaState !== 'idle' && selectedFile !== null;
    return () => {
      delete win.__mediaPickerSendMethod;
      delete win.__mediaPickerHasMedia;
    };
  }, [selectedFile, mediaState, photoDimensions, videoDuration, videoThumbnail]);

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

      {/* Always show buttons — clicking when media is selected replaces it */}
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

      {/* Error display */}
      {error && (
        <span className="text-xs text-red-500">{error}</span>
      )}
    </div>
  );
}
