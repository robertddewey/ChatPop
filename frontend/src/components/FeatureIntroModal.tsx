'use client';

import React from 'react';
import { createPortal } from 'react-dom';
import { LucideIcon } from 'lucide-react';

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

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onDismiss}
    >
      <div
        className={`mx-6 max-w-sm w-full rounded-2xl p-6 shadow-xl ${
          isDark ? 'bg-zinc-900 text-zinc-50' : 'bg-white text-gray-900'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-col items-center text-center gap-4">
          <div className={`w-14 h-14 rounded-full flex items-center justify-center ${
            isDark ? 'bg-zinc-800' : 'bg-gray-100'
          }`}>
            <Icon className={`w-7 h-7 ${isDark ? 'text-cyan-400' : 'text-blue-500'}`} />
          </div>

          <h2 className="text-lg font-semibold">{title}</h2>

          <p className={`text-sm leading-relaxed ${
            isDark ? 'text-zinc-400' : 'text-gray-600'
          }`}>
            {description}
          </p>

          <button
            onClick={onDismiss}
            className={`w-full mt-2 py-2.5 rounded-xl font-medium text-sm transition-colors ${
              isDark
                ? 'bg-zinc-700 hover:bg-zinc-600 text-zinc-50'
                : 'bg-gray-100 hover:bg-gray-200 text-gray-900'
            }`}
          >
            Got it
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
