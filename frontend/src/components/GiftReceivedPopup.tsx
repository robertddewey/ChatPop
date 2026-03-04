'use client';

import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import type { GiftNotification } from '@/lib/api';
import { formatGiftPrice, getGiftBulkActionThreshold } from '@/lib/gifts';

interface GiftReceivedPopupProps {
  gifts: GiftNotification[];
  themeIsDarkMode?: boolean;
  onSkipOne: (giftId: string) => void;
  onThankOne: (giftId: string) => void;
  onSkipAll: () => void;
  onThankAll: () => void;
  onClose: () => void;
}

export function GiftReceivedPopup({
  gifts,
  themeIsDarkMode = true,
  onSkipOne,
  onThankOne,
  onSkipAll,
  onThankAll,
  onClose,
}: GiftReceivedPopupProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (gifts.length > 0) {
      // Small delay for entrance animation
      requestAnimationFrame(() => setIsVisible(true));
    } else {
      setIsVisible(false);
    }
  }, [gifts.length]);

  if (!mounted || gifts.length === 0) return null;

  const currentGift = gifts[0];
  const totalCount = gifts.length;
  const showBulkActions = totalCount >= getGiftBulkActionThreshold();

  const isDark = themeIsDarkMode;

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      onClick={(e) => e.stopPropagation()}
    >
      {/* Backdrop */}
      <div
        className={`absolute inset-0 transition-opacity duration-300 ${
          isVisible ? 'opacity-100' : 'opacity-0'
        } ${isDark ? 'bg-black/60 backdrop-blur-sm' : 'bg-black/30 backdrop-blur-sm'}`}
      />

      {/* Card */}
      <div
        className={`relative transition-all duration-300 ${
          isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-90'
        } rounded-2xl shadow-2xl p-6 mx-6 max-w-sm w-full text-center ${
          isDark ? 'bg-zinc-900 border border-zinc-700' : 'bg-white border border-gray-200'
        }`}
      >
        {/* Queue counter — top-left corner */}
        {totalCount > 1 && (
          <div className={`absolute top-3 left-4 text-xs font-medium ${isDark ? 'text-zinc-400' : 'text-gray-500'}`}>
            1 of {totalCount}
          </div>
        )}

        {/* Close button — top-right corner */}
        <button
          onClick={onClose}
          className={`absolute top-3 right-3 p-1 rounded-full transition-colors ${
            isDark ? 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
          }`}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>

        {/* Gift emoji */}
        <div className="text-7xl mb-3 animate-gift-breath">
          {currentGift.emoji}
        </div>

        {/* Gift name */}
        <div className={`text-xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
          {currentGift.name}
        </div>

        {/* Price */}
        <div className={`text-2xl font-bold mb-2 ${isDark ? 'text-cyan-400' : 'text-purple-600'}`}>
          {formatGiftPrice(currentGift.price_cents)}
        </div>

        {/* From */}
        <div className={`text-sm mb-5 ${isDark ? 'text-zinc-400' : 'text-gray-500'}`}>
          from <span className={`font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>@{currentGift.sender_username}</span>
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={() => showBulkActions ? onSkipAll() : onSkipOne(currentGift.id)}
            className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${
              isDark ? 'bg-zinc-700 hover:bg-zinc-600 text-zinc-200' : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
            }`}
          >
            {showBulkActions ? 'Skip All' : 'Skip'}
          </button>
          <button
            onClick={() => showBulkActions ? onThankAll() : onThankOne(currentGift.id)}
            className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${
              isDark ? 'bg-[#404eed] hover:bg-[#3640d9] text-white' : 'bg-purple-600 hover:bg-purple-500 text-white'
            }`}
          >
            {showBulkActions ? 'Thank All' : 'Thank you!'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
