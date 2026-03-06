'use client';

import React from 'react';
import { createPortal } from 'react-dom';
import { LucideIcon } from 'lucide-react';
import { getModalTheme } from '@/lib/modal-theme';

interface FeatureIntroModalProps {
  title: string;
  description: string;
  icon: LucideIcon;
  themeIsDarkMode: boolean;
  onDismiss: () => void;
}

export default function FeatureIntroModal({
  title,
  description,
  icon: Icon,
  themeIsDarkMode,
  onDismiss,
}: FeatureIntroModalProps) {
  const isDark = themeIsDarkMode;
  const mt = getModalTheme(isDark);

  return createPortal(
    <div
      className={`fixed inset-0 z-[9999] flex items-center justify-center ${mt.backdrop}`}
      onClick={onDismiss}
    >
      <div
        className={`mx-6 max-w-sm w-full ${mt.rounded} p-6 ${mt.shadow} ${mt.container} ${mt.title}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-col items-center text-center gap-4">
          <div className={`w-14 h-14 rounded-full flex items-center justify-center ${
            isDark ? 'bg-zinc-800' : 'bg-gray-100'
          }`}>
            <Icon className={`w-7 h-7 ${isDark ? 'text-cyan-400' : 'text-blue-500'}`} />
          </div>

          <h2 className="text-lg font-semibold">{title}</h2>

          <p className={`text-sm leading-relaxed ${mt.body}`}>
            {description}
          </p>

          <button
            onClick={onDismiss}
            className={`w-full mt-2 py-2.5 rounded-xl font-medium text-sm transition-colors ${mt.secondaryButton}`}
          >
            Got it
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
