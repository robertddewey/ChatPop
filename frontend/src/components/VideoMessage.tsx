'use client';

import React, { useState, useRef } from 'react';
import { Play, Pause, X, Maximize2 } from 'lucide-react';

interface VideoMessageProps {
  videoUrl: string;
  thumbnailUrl: string;
  duration: number;
  className?: string;
  maxDisplayWidth?: number;
  maxDisplayHeight?: number;
}

// Global video manager to ensure only one video plays at a time
class GlobalVideoManager {
  private static currentVideo: HTMLVideoElement | null = null;
  private static currentStopCallback: (() => void) | null = null;

  static play(video: HTMLVideoElement, stopCallback: () => void) {
    if (this.currentVideo && this.currentVideo !== video) {
      this.currentVideo.pause();
      if (this.currentStopCallback) {
        this.currentStopCallback();
      }
    }
    this.currentVideo = video;
    this.currentStopCallback = stopCallback;
  }

  static stop(video: HTMLVideoElement) {
    if (this.currentVideo === video) {
      this.currentVideo = null;
      this.currentStopCallback = null;
    }
  }
}

export default function VideoMessage({
  videoUrl,
  thumbnailUrl,
  duration,
  className = '',
  maxDisplayWidth = 280,
  maxDisplayHeight = 320,
}: VideoMessageProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const fullscreenVideoRef = useRef<HTMLVideoElement>(null);

  // Default 16:9 aspect ratio if dimensions not known
  const aspectRatio = 16 / 9;
  let displayWidth = maxDisplayWidth;
  let displayHeight = displayWidth / aspectRatio;

  if (displayHeight > maxDisplayHeight) {
    displayHeight = maxDisplayHeight;
    displayWidth = displayHeight * aspectRatio;
  }

  const formatTime = (seconds: number): string => {
    if (!isFinite(seconds) || seconds < 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const togglePlayPause = async () => {
    const video = isFullscreen ? fullscreenVideoRef.current : videoRef.current;
    if (!video) return;

    try {
      if (isPlaying) {
        video.pause();
        setIsPlaying(false);
        GlobalVideoManager.stop(video);
      } else {
        setIsLoading(true);
        GlobalVideoManager.play(video, () => {
          setIsPlaying(false);
        });
        await video.play();
        setIsPlaying(true);
        setIsLoading(false);
      }
    } catch (error) {
      console.error('[VideoMessage] Playback error:', error);
      setIsPlaying(false);
      setIsLoading(false);
      setHasError(true);
    }
  };

  const handleTimeUpdate = () => {
    const video = isFullscreen ? fullscreenVideoRef.current : videoRef.current;
    if (video) {
      setCurrentTime(video.currentTime);
    }
  };

  const handleVideoEnd = () => {
    setIsPlaying(false);
    setCurrentTime(0);
    const video = isFullscreen ? fullscreenVideoRef.current : videoRef.current;
    if (video) {
      video.currentTime = 0;
      GlobalVideoManager.stop(video);
    }
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const video = isFullscreen ? fullscreenVideoRef.current : videoRef.current;
    if (!video) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percentage = clickX / rect.width;
    const newTime = percentage * duration;

    video.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const openFullscreen = () => {
    // Pause inline video if playing
    if (videoRef.current && isPlaying) {
      videoRef.current.pause();
    }
    setIsFullscreen(true);
    document.body.style.overflow = 'hidden';
  };

  const closeFullscreen = () => {
    // Pause fullscreen video if playing
    if (fullscreenVideoRef.current) {
      fullscreenVideoRef.current.pause();
      GlobalVideoManager.stop(fullscreenVideoRef.current);
    }
    setIsFullscreen(false);
    setIsPlaying(false);
    document.body.style.overflow = '';
  };

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  if (hasError) {
    return (
      <div
        className={`flex items-center justify-center bg-gray-100 dark:bg-zinc-800 rounded-lg text-gray-500 dark:text-gray-400 text-sm max-w-full ${className}`}
        style={{ width: displayWidth, height: displayHeight, maxWidth: '100%' }}
      >
        Failed to load video
      </div>
    );
  }

  return (
    <>
      {/* Inline video player */}
      <div
        className={`relative rounded-lg overflow-hidden bg-black max-w-full ${className}`}
        style={{ width: displayWidth, height: displayHeight, maxWidth: '100%' }}
      >
        {/* Video element (hidden until playing) */}
        <video
          ref={videoRef}
          src={videoUrl}
          poster={thumbnailUrl}
          className="w-full h-full object-contain"
          playsInline
          onTimeUpdate={handleTimeUpdate}
          onEnded={handleVideoEnd}
          onError={() => setHasError(true)}
        />

        {/* Play overlay (shown when not playing) */}
        {!isPlaying && (
          <div
            className="absolute inset-0 flex items-center justify-center cursor-pointer"
            onClick={togglePlayPause}
          >
            {/* Thumbnail background */}
            <div
              className="absolute inset-0 bg-contain bg-center bg-no-repeat"
              style={{ backgroundImage: `url(${thumbnailUrl})` }}
            />
            {/* Dark overlay */}
            <div className="absolute inset-0 bg-black/30" />
            {/* Play button */}
            <div className="relative z-10 w-12 h-12 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-gray-600 border-t-transparent rounded-full animate-spin" />
              ) : (
                <Play size={20} className="text-gray-800 ml-1" fill="currentColor" />
              )}
            </div>
          </div>
        )}

        {/* Controls overlay (shown when playing) */}
        {isPlaying && (
          <div
            className="absolute inset-0 flex items-center justify-center cursor-pointer group"
            onClick={togglePlayPause}
          >
            {/* Pause button on hover */}
            <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              <Pause size={32} className="text-white" fill="white" />
            </div>
          </div>
        )}

        {/* Duration badge */}
        <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/70 text-white text-xs font-mono">
          {formatTime(isPlaying ? currentTime : duration)}
        </div>

        {/* Fullscreen button */}
        <button
          className="absolute top-2 right-2 p-1.5 rounded bg-black/50 text-white hover:bg-black/70 transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            openFullscreen();
          }}
          aria-label="Open fullscreen"
        >
          <Maximize2 size={14} />
        </button>

        {/* Progress bar */}
        {isPlaying && (
          <div
            className="absolute bottom-0 left-0 right-0 h-1 bg-black/30 cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
              handleSeek(e);
            }}
          >
            <div
              className="h-full bg-white transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>

      {/* Fullscreen video player */}
      {isFullscreen && (
        <div
          className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center"
          onClick={closeFullscreen}
        >
          {/* Close button */}
          <button
            className="absolute top-4 right-4 p-2 rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors z-10"
            onClick={closeFullscreen}
            aria-label="Close fullscreen"
          >
            <X size={24} />
          </button>

          {/* Full-size video */}
          <video
            ref={fullscreenVideoRef}
            src={videoUrl}
            className="max-w-[95vw] max-h-[85vh] object-contain"
            playsInline
            controls
            onClick={(e) => e.stopPropagation()}
            onTimeUpdate={handleTimeUpdate}
            onEnded={handleVideoEnd}
          />
        </div>
      )}
    </>
  );
}
