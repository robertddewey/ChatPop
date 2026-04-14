'use client';

import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import type { GiftNotification } from '@/lib/api';
import { formatGiftPrice, getGiftBulkActionThreshold } from '@/lib/gifts';
import { getModalTheme } from '@/lib/modal-theme';

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
  const mt = getModalTheme(isDark);

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      onClick={(e) => e.stopPropagation()}
    >
      {/* Wrapper — extra level keeps card out of body.chat-layout > * > *
          transparency rule, so mt.container / mt.backdrop bg classes apply. */}
      <div className="relative w-full flex items-center justify-center">
        {/* Backdrop */}
        <div
          className={`fixed inset-0 transition-opacity duration-300 ${
            isVisible ? 'opacity-100' : 'opacity-0'
          } ${mt.backdrop}`}
        />

        {/* Card */}
        <div
          className={`relative transition-all duration-300 ${
            isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-90'
          } ${mt.rounded} ${mt.shadow} p-6 mx-6 max-w-sm w-full text-center ${mt.container} ${mt.border}`}
        >
          {/* Queue counter — top-left corner */}
          {totalCount > 1 && (
            <div className={`absolute top-3 left-4 text-xs font-medium ${mt.body}`}>
              1 of {totalCount}
            </div>
          )}

          {/* Close button — top-right corner */}
          <button
            onClick={onClose}
            className={`absolute top-3 right-3 p-1 rounded-full transition-colors ${mt.closeButton}`}
          >
            <X size={16} />
          </button>

        {/* Gift emoji */}
          <div className="text-7xl mb-3 animate-gift-breath">
            {currentGift.emoji}
          </div>

          {/* Gift name */}
          <div className={`text-xl font-bold mb-1 ${mt.title}`}>
            {currentGift.name}
          </div>

          {/* Price */}
          <div className={`text-2xl font-bold mb-2 ${isDark ? 'text-cyan-400' : 'text-purple-600'}`}>
            {formatGiftPrice(currentGift.price_cents)}
          </div>

          {/* From */}
          <div className={`text-sm mb-5 ${mt.body}`}>
            from <span className={`font-semibold ${mt.title}`}>@{currentGift.sender_username}</span>
          </div>

          {/* Buttons */}
          <div className="flex gap-3">
            <button
              onClick={() => showBulkActions ? onSkipAll() : onSkipOne(currentGift.id)}
              className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${mt.secondaryButton}`}
            >
              {showBulkActions ? 'Skip All' : 'Skip'}
            </button>
            <button
              onClick={() => showBulkActions ? onThankAll() : onThankOne(currentGift.id)}
              className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${mt.primaryButton}`}
            >
              {showBulkActions ? 'Thank All' : 'Thank you!'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
