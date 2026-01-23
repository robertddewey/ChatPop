'use client';

import React, { useState } from 'react';
import { X, ZoomIn } from 'lucide-react';

interface PhotoMessageProps {
  photoUrl: string;
  width: number;
  height: number;
  className?: string;
  maxDisplayWidth?: number;
  maxDisplayHeight?: number;
}

export default function PhotoMessage({
  photoUrl,
  width,
  height,
  className = '',
  maxDisplayWidth = 280,
  maxDisplayHeight = 320,
}: PhotoMessageProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  // Calculate display dimensions maintaining aspect ratio
  const aspectRatio = width / height;
  let displayWidth = width;
  let displayHeight = height;

  if (displayWidth > maxDisplayWidth) {
    displayWidth = maxDisplayWidth;
    displayHeight = displayWidth / aspectRatio;
  }

  if (displayHeight > maxDisplayHeight) {
    displayHeight = maxDisplayHeight;
    displayWidth = displayHeight * aspectRatio;
  }

  const handleImageLoad = () => {
    setIsLoading(false);
  };

  const handleImageError = () => {
    setIsLoading(false);
    setHasError(true);
  };

  const openFullscreen = () => {
    setIsFullscreen(true);
    // Prevent body scroll when fullscreen is open
    document.body.style.overflow = 'hidden';
  };

  const closeFullscreen = () => {
    setIsFullscreen(false);
    document.body.style.overflow = '';
  };

  if (hasError) {
    return (
      <div
        className={`flex items-center justify-center bg-gray-100 dark:bg-zinc-800 rounded-lg text-gray-500 dark:text-gray-400 text-sm ${className}`}
        style={{ width: displayWidth, height: displayHeight }}
      >
        Failed to load image
      </div>
    );
  }

  return (
    <>
      {/* Thumbnail in message */}
      <div
        className={`relative rounded-lg overflow-hidden cursor-pointer group ${className}`}
        style={{ width: displayWidth, height: displayHeight }}
        onClick={openFullscreen}
      >
        {isLoading && (
          <div className="absolute inset-0 bg-gray-100 dark:bg-zinc-800 animate-pulse" />
        )}
        <img
          src={photoUrl}
          alt="Photo message"
          className={`w-full h-full object-cover transition-opacity ${isLoading ? 'opacity-0' : 'opacity-100'}`}
          onLoad={handleImageLoad}
          onError={handleImageError}
          loading="lazy"
        />
        {/* Zoom overlay on hover */}
        <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <ZoomIn size={24} className="text-white" />
        </div>
      </div>

      {/* Fullscreen lightbox */}
      {isFullscreen && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
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

          {/* Full-size image */}
          <img
            src={photoUrl}
            alt="Photo message fullscreen"
            className="max-w-[95vw] max-h-[95vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
}
