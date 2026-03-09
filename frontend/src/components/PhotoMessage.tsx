'use client';

import React, { useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { ZoomIn } from 'lucide-react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';

interface PhotoMessageProps {
  photoUrl: string;
  width: number;
  height: number;
  caption?: string;
  captionClassName?: string;
  className?: string;
  maxDisplayWidth?: number;
  maxDisplayHeight?: number;
}

export default function PhotoMessage({
  photoUrl,
  width,
  height,
  caption,
  captionClassName = '',
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
        className={`flex items-center justify-center bg-gray-100 dark:bg-zinc-800 rounded-lg text-gray-500 dark:text-gray-400 text-sm max-w-full ${className}`}
        style={{ width: displayWidth, maxWidth: '100%', aspectRatio: `${displayWidth} / ${displayHeight}` }}
      >
        Failed to load image
      </div>
    );
  }

  return (
    <>
      {/* Photo container with optional caption */}
      <div className="flex flex-col gap-1.5">
        {/* Caption - above the photo like regular text messages */}
        {caption && (
          <p className={`text-sm ${captionClassName}`}>
            {caption}
          </p>
        )}

        {/* Thumbnail in message */}
        <div
          className={`relative rounded-lg overflow-hidden cursor-pointer group max-w-full ${className}`}
          style={{ width: displayWidth, maxWidth: '100%', aspectRatio: `${displayWidth} / ${displayHeight}` }}
          onClick={openFullscreen}
        >
          {isLoading && (
            <div className="absolute inset-0 bg-gray-100 dark:bg-zinc-800 animate-pulse" />
          )}
          <img
            src={photoUrl}
            alt="Photo message"
            className={`w-full h-full object-contain transition-opacity ${isLoading ? 'opacity-0' : 'opacity-100'}`}
            onLoad={handleImageLoad}
            onError={handleImageError}
            loading="lazy"
            draggable={false}
          />
          {/* Zoom overlay on hover */}
          <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <ZoomIn size={24} className="text-white" />
          </div>
        </div>
      </div>

      {/* Fullscreen lightbox with pinch-to-zoom — portal to body to escape stacking contexts */}
      {isFullscreen && createPortal(
        <FullscreenViewer photoUrl={photoUrl} onClose={closeFullscreen} />,
        document.body
      )}
    </>
  );
}

function FullscreenViewer({ photoUrl, onClose }: { photoUrl: string; onClose: () => void }) {
  const touchStartY = useRef<number | null>(null);
  const currentScale = useRef(1);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    e.stopPropagation();
    if (e.touches.length === 1 && currentScale.current <= 1) {
      touchStartY.current = e.touches[0].clientY;
    }
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    e.stopPropagation();
  }, []);

  const handleTouchEnd = useCallback((e: React.TouchEvent) => {
    e.stopPropagation();
    if (touchStartY.current !== null && e.changedTouches.length === 1 && currentScale.current <= 1) {
      const deltaY = e.changedTouches[0].clientY - touchStartY.current;
      if (deltaY > 100) {
        onClose();
      }
    }
    touchStartY.current = null;
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[60] bg-black flex items-center justify-center"
      style={{ touchAction: 'none' }}
      onClick={onClose}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Zoomable image */}
      <TransformWrapper
        initialScale={1}
        minScale={1}
        maxScale={4}
        doubleClick={{ mode: 'toggle', step: 2 }}
        onTransformed={(_ref, state) => { currentScale.current = state.scale; }}
        panning={{ disabled: false }}
        wheel={{ step: 0.5 }}
        centerOnInit
      >
        <TransformComponent
          wrapperStyle={{ width: '100vw', height: '100vh' }}
          contentStyle={{ width: '100vw', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <img
            src={photoUrl}
            alt="Photo message fullscreen"
            className="max-w-[100vw] max-h-[100vh] object-contain"
            draggable={false}
            onClick={(e) => e.stopPropagation()}
          />
        </TransformComponent>
      </TransformWrapper>
    </div>
  );
}
