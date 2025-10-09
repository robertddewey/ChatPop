'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { chatApi, type ChatRoom } from '@/lib/api';
import { Copy, Check, BadgeCheck, Moon, Sun } from 'lucide-react';
import { migrateLegacyTheme, DEFAULT_THEME, type ThemeId, isDarkTheme } from '@/lib/themes';

// Theme color constants for optimistic updates
// IMPORTANT: For both themes, light and dark values MUST be the same
// to override system preference and force the browser chrome color
const THEME_COLORS = {
  'dark-mode': {
    light: '#18181b', // zinc-900 (both same - force dark)
    dark: '#18181b',  // zinc-900
  },
  'light-mode': {
    light: '#ffffff', // white (both same - force light)
    dark: '#ffffff',  // white (NOT gray-800 - must match to override system dark mode)
  },
} as const;

// Helper function to update theme-color meta tags (iOS Safari requirement)
// IMPORTANT: For light-mode theme, we force BOTH light and dark to white (#ffffff)
// because iOS Safari uses the dark meta tag when system is in dark mode,
// but we want to override system preference with our theme choice.
const updateThemeColorMetaTags = (themeColors: { light: string; dark: string }) => {
  if (typeof window === 'undefined' || typeof document === 'undefined') return;

  // For light-mode theme: force both to the light color (white)
  // For dark-mode theme: both are already the same (zinc-900)
  // This ensures the theme color matches the theme, not the system preference
  const forcedLightColor = themeColors.light;
  const forcedDarkColor = themeColors.light; // Use light color for dark too (override system)

  // Update default meta tag
  let defaultMeta = document.querySelector('meta[name="theme-color"]:not([media])') as HTMLMetaElement;
  if (defaultMeta) {
    defaultMeta.content = forcedLightColor;
  } else {
    defaultMeta = document.createElement('meta');
    defaultMeta.name = 'theme-color';
    defaultMeta.content = forcedLightColor;
    document.head.appendChild(defaultMeta);
  }

  // Update light mode meta tag (use light color)
  let lightMeta = document.querySelector('meta[name="theme-color"][media="(prefers-color-scheme: light)"]') as HTMLMetaElement;
  if (lightMeta) {
    lightMeta.content = forcedLightColor;
  } else {
    lightMeta = document.createElement('meta');
    lightMeta.name = 'theme-color';
    lightMeta.setAttribute('media', '(prefers-color-scheme: light)');
    lightMeta.content = forcedLightColor;
    document.head.appendChild(lightMeta);
  }

  // Update dark mode meta tag (ALSO use light color to override system dark mode)
  let darkMeta = document.querySelector('meta[name="theme-color"][media="(prefers-color-scheme: dark)"]') as HTMLMetaElement;
  if (darkMeta) {
    darkMeta.content = forcedDarkColor;
  } else {
    darkMeta = document.createElement('meta');
    darkMeta.name = 'theme-color';
    darkMeta.setAttribute('media', '(prefers-color-scheme: dark)');
    darkMeta.content = forcedDarkColor;
    document.head.appendChild(darkMeta);
  }
};

interface ChatSettingsSheetProps {
  chatRoom: ChatRoom;
  currentUserId?: string;
  fingerprint?: string;
  activeThemeId?: string;
  onUpdate?: (chatRoom: ChatRoom) => void;
  onThemeChange?: (theme: ThemeId) => void;
  themeIsDarkMode?: boolean;
  children: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export default function ChatSettingsSheet({
  chatRoom,
  currentUserId,
  fingerprint,
  activeThemeId,
  onUpdate,
  onThemeChange,
  themeIsDarkMode = true,
  children,
  open,
  onOpenChange,
}: ChatSettingsSheetProps) {
  const router = useRouter();
  const isHost = chatRoom.host.id === currentUserId;

  // Theme-aware styles (no system preference detection - force theme mode)
  const styles = themeIsDarkMode ? {
    title: '!text-white',
    subtitle: '!text-zinc-400',
    text: '!text-white',
    subtext: '!text-gray-400',
    input: 'bg-zinc-800 border-zinc-700 !text-zinc-100 focus:ring-cyan-400',
    card: 'bg-zinc-800',
    button: 'bg-cyan-400 hover:bg-cyan-500 text-cyan-950',
    border: 'border-zinc-700',
  } : {
    title: '!text-gray-900',
    subtitle: '!text-gray-600',
    text: '!text-black',
    subtext: '!text-gray-500',
    input: 'bg-white border-gray-300 !text-gray-900 focus:ring-purple-500',
    card: 'bg-gray-50',
    button: 'bg-purple-600 hover:bg-purple-700 text-white',
    border: 'border-gray-200',
  };

  // Use controlled state if provided, otherwise use internal state
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const isOpen = open !== undefined ? open : internalIsOpen;
  const setIsOpen = onOpenChange || setInternalIsOpen;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [copiedCode, setCopiedCode] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  // Form state (only for host)
  const [formData, setFormData] = useState({
    name: chatRoom.name,
    description: chatRoom.description,
    access_mode: chatRoom.access_mode,
    access_code: '',
    voice_enabled: chatRoom.voice_enabled,
    video_enabled: chatRoom.video_enabled,
    photo_enabled: chatRoom.photo_enabled,
  });

  const handleCopyCode = () => {
    navigator.clipboard.writeText(chatRoom.code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleCopyLink = () => {
    const link = `${window.location.origin}/chat/${chatRoom.code}`;
    navigator.clipboard.writeText(link);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isHost) return;

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const updatedRoom = await chatApi.updateChat(chatRoom.code, formData);
      setSuccess('Settings updated successfully!');
      onUpdate?.(updatedRoom);
      setTimeout(() => {
        setSuccess('');
        setIsOpen(false);
      }, 1500);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update settings');
    } finally {
      setLoading(false);
    }
  };

  const shareLink = `${typeof window !== 'undefined' ? window.location.origin : ''}/chat/${chatRoom.code}`;

  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetTrigger asChild>{children}</SheetTrigger>
      <SheetContent
        side="bottom"
        className={`h-[100dvh] overflow-y-auto pt-2 ${
          themeIsDarkMode
            ? 'bg-zinc-900 border-t-zinc-800'
            : 'bg-white border-t-white'
        }`}
        closeButtonClassName={themeIsDarkMode ? '!text-white' : '!text-gray-900'}
      >
          <SheetHeader>
            <SheetTitle className={styles.title}>
              Chat Settings
            </SheetTitle>
            <SheetDescription className={styles.subtitle}>
              {isHost ? 'Manage your chat room settings' : 'Chat room information'}
            </SheetDescription>
          </SheetHeader>

          <div className="mt-6 space-y-6">
          {/* Theme Selection */}
          <div className="space-y-4">
            <h3 className={`text-sm font-semibold ${styles.title}`}>
              Change Theme <span className={`text-xs font-normal ${themeIsDarkMode ? 'text-gray-500' : 'text-gray-500'}`}>(will reload the chat)</span> {chatRoom.theme_locked && <span className={`text-xs font-normal ${styles.subtext}`}>(locked by host)</span>}
            </h3>

            <div className="grid grid-cols-3 gap-3">
              {/* Dark Mode */}
              <button
                onClick={async () => {
                  if (chatRoom.theme_locked) return;

                  // Store current theme for rollback on error
                  const currentThemeColors = localStorage.getItem('chat_theme_color');

                  try {
                    // Start API call
                    const apiPromise = chatApi.updateMyTheme(chatRoom.code, 'dark-mode', fingerprint);

                    // Optimistically update localStorage immediately with known colors
                    localStorage.setItem('chat_theme_color', JSON.stringify(THEME_COLORS['dark-mode']));

                    // Update theme-color meta tags immediately (iOS Safari requirement)
                    updateThemeColorMetaTags(THEME_COLORS['dark-mode']);

                    // Wait for API OR timeout (whichever comes first)
                    const result = await Promise.race([
                      apiPromise.then(() => ({ success: true })),
                      new Promise(resolve => setTimeout(() => resolve({ timeout: true }), 200))
                    ]);

                    // Reload to apply theme (API succeeded or is still processing)
                    window.location.reload();
                  } catch (err) {
                    // API failed - revert localStorage to prevent mismatch
                    if (currentThemeColors) {
                      localStorage.setItem('chat_theme_color', currentThemeColors);
                      // Revert meta tags too
                      try {
                        const parsed = JSON.parse(currentThemeColors);
                        updateThemeColorMetaTags(parsed);
                      } catch (e) {
                        // Ignore parse errors
                      }
                    } else {
                      localStorage.removeItem('chat_theme_color');
                    }
                    console.error('Failed to update theme:', err);
                    // Don't reload - keep user in current state
                  }
                }}
                disabled={chatRoom.theme_locked || activeThemeId === 'dark-mode'}
                className={`p-3 rounded-lg transition-all focus:outline-none border-2 bg-zinc-950 ${
                  activeThemeId === 'dark-mode'
                    ? 'border-cyan-400 bg-cyan-400/10'
                    : 'border-zinc-800 hover:border-cyan-400/50'
                } ${chatRoom.theme_locked ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-semibold text-white">Dark Mode</div>
                  <div className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-zinc-800 text-zinc-300">
                    <Moon size={10} />
                    <span>Dark</span>
                  </div>
                </div>
                <div className="h-8 rounded bg-zinc-950 flex items-center justify-center gap-1">
                  <div className="h-4 w-12 rounded bg-cyan-400"></div>
                  <div className="h-4 w-8 rounded bg-yellow-400"></div>
                </div>
              </button>

              {/* Light Mode */}
              <button
                onClick={async () => {
                  if (chatRoom.theme_locked) return;

                  // Store current theme for rollback on error
                  const currentThemeColors = localStorage.getItem('chat_theme_color');

                  try {
                    // Start API call
                    const apiPromise = chatApi.updateMyTheme(chatRoom.code, 'light-mode', fingerprint);

                    // Optimistically update localStorage immediately with known colors
                    localStorage.setItem('chat_theme_color', JSON.stringify(THEME_COLORS['light-mode']));

                    // Update theme-color meta tags immediately (iOS Safari requirement)
                    updateThemeColorMetaTags(THEME_COLORS['light-mode']);

                    // Wait for API OR timeout (whichever comes first)
                    const result = await Promise.race([
                      apiPromise.then(() => ({ success: true })),
                      new Promise(resolve => setTimeout(() => resolve({ timeout: true }), 200))
                    ]);

                    // Reload to apply theme (API succeeded or is still processing)
                    window.location.reload();
                  } catch (err) {
                    // API failed - revert localStorage to prevent mismatch
                    if (currentThemeColors) {
                      localStorage.setItem('chat_theme_color', currentThemeColors);
                      // Revert meta tags too
                      try {
                        const parsed = JSON.parse(currentThemeColors);
                        updateThemeColorMetaTags(parsed);
                      } catch (e) {
                        // Ignore parse errors
                      }
                    } else {
                      localStorage.removeItem('chat_theme_color');
                    }
                    console.error('Failed to update theme:', err);
                    // Don't reload - keep user in current state
                  }
                }}
                disabled={chatRoom.theme_locked || activeThemeId === 'light-mode'}
                className={`p-3 rounded-lg transition-all focus:outline-none border-2 bg-white ${
                  activeThemeId === 'light-mode'
                    ? 'border-blue-500 bg-blue-500/10'
                    : 'border-gray-300 hover:border-blue-500/50'
                } ${chatRoom.theme_locked ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-semibold text-gray-900">Light Mode</div>
                  <div className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-gray-100 text-gray-700">
                    <Sun size={10} />
                    <span>Light</span>
                  </div>
                </div>
                <div className="h-8 rounded bg-gray-50 border border-gray-200 flex items-center justify-center gap-1">
                  <div className="h-4 w-12 rounded bg-blue-500"></div>
                  <div className="h-4 w-8 rounded bg-gray-300"></div>
                </div>
              </button>

              {/* Placeholder for future theme */}
              <div className={`p-3 rounded-lg border-2 border-dashed ${styles.border} opacity-30`}>
                <div className="flex items-center justify-center h-full">
                  <span className={`text-xs ${styles.subtext}`}>Coming Soon</span>
                </div>
              </div>
            </div>
          </div>

          {/* Chat Information for All Users */}
          <div className={`space-y-4 pt-4 border-t ${styles.border}`}>
            <h3 className={`text-sm font-semibold ${styles.title}`}>
              Chat Information
            </h3>

            {/* Chat Name */}
            <div className={`p-3 rounded-lg ${styles.card}`}>
              <p className={`text-xs ${styles.subtext}`}>Chat Name</p>
              <p className={`text-sm font-semibold ${styles.text}`}>
                {chatRoom.name}
              </p>
            </div>

            {/* Chat Code */}
            <div className={`flex items-center justify-between p-3 rounded-lg ${styles.card}`}>
              <div>
                <p className={`text-xs ${styles.subtext}`}>Chat Code</p>
                <p className={`text-sm font-mono font-semibold ${styles.text}`}>{chatRoom.code}</p>
              </div>
              <button
                onClick={handleCopyCode}
                className={`p-2 rounded-lg transition-colors ${themeIsDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-200'}`}
              >
                {copiedCode ? (
                  <Check className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className={`w-4 h-4 ${themeIsDarkMode ? 'text-gray-400' : 'text-gray-600'}`} />
                )}
              </button>
            </div>

            {/* Share Link */}
            <div className={`flex items-center justify-between p-3 rounded-lg ${styles.card}`}>
              <div className="flex-1 min-w-0">
                <p className={`text-xs ${styles.subtext}`}>Share Link</p>
                <p className={`text-sm font-mono truncate ${styles.text}`}>{shareLink}</p>
              </div>
              <button
                onClick={handleCopyLink}
                className={`ml-2 p-2 rounded-lg transition-colors flex-shrink-0 ${themeIsDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-200'}`}
              >
                {copiedLink ? (
                  <Check className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className={`w-4 h-4 ${themeIsDarkMode ? 'text-gray-400' : 'text-gray-600'}`} />
                )}
              </button>
            </div>

            {/* Host Info */}
            <div className={`p-3 rounded-lg ${styles.card}`}>
              <p className={`text-xs ${styles.subtext}`}>Hosted by</p>
              <div className="flex items-center gap-1.5">
                <p className={`text-sm font-semibold ${styles.text}`}>
                  {chatRoom.host.reserved_username || chatRoom.host.email.split('@')[0]}
                </p>
                {chatRoom.host.reserved_username && (
                  <BadgeCheck className="text-blue-500 flex-shrink-0" size={16} />
                )}
              </div>
            </div>

            {/* Created Date */}
            <div className={`p-3 rounded-lg ${styles.card}`}>
              <p className={`text-xs ${styles.subtext}`}>Created</p>
              <p className={`text-sm ${styles.text}`}>
                {new Date(chatRoom.created_at).toLocaleDateString('en-US', {
                  month: 'long',
                  day: 'numeric',
                  year: 'numeric',
                })}
              </p>
            </div>
          </div>

          {/* Host-Only Settings */}
          {isHost && (
            <form onSubmit={handleSubmit} className={`space-y-4 pt-4 border-t ${styles.border}`}>
              <h3 className={`text-sm font-semibold ${styles.title}`}>
                Edit Settings (Host Only)
              </h3>

              {error && (
                <div className={`p-3 rounded-lg text-sm ${themeIsDarkMode ? 'bg-red-900/20 border border-red-800 text-red-400' : 'bg-red-50 border border-red-200 text-red-600'}`}>
                  {error}
                </div>
              )}

              {success && (
                <div className={`p-3 rounded-lg text-sm ${themeIsDarkMode ? 'bg-green-900/20 border border-green-800 text-green-400' : 'bg-green-50 border border-green-200 text-green-600'}`}>
                  {success}
                </div>
              )}

              {/* Chat Name */}
              <div>
                <label className={`block text-sm font-medium mb-1 ${themeIsDarkMode ? 'text-zinc-300' : 'text-gray-700'}`}>
                  Chat Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${styles.input}`}
                  required
                />
              </div>

              {/* Access Mode */}
              <div>
                <label className={`block text-sm font-medium mb-2 ${themeIsDarkMode ? 'text-zinc-300' : 'text-gray-700'}`}>
                  Access Mode
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="radio"
                      value="public"
                      checked={formData.access_mode === 'public'}
                      onChange={(e) =>
                        setFormData({ ...formData, access_mode: e.target.value as 'public' | 'private' })
                      }
                      className={themeIsDarkMode ? 'mr-2 text-cyan-400 focus:ring-cyan-400' : 'mr-2 text-purple-600 focus:ring-purple-500'}
                    />
                    <span className={`text-sm ${styles.text}`}>Public</span>
                  </label>
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="radio"
                      value="private"
                      checked={formData.access_mode === 'private'}
                      onChange={(e) =>
                        setFormData({ ...formData, access_mode: e.target.value as 'public' | 'private' })
                      }
                      className={themeIsDarkMode ? 'mr-2 text-cyan-400 focus:ring-cyan-400' : 'mr-2 text-purple-600 focus:ring-purple-500'}
                    />
                    <span className={`text-sm ${styles.text}`}>Private</span>
                  </label>
                </div>
              </div>

              {/* Access Code (if private) */}
              {formData.access_mode === 'private' && (
                <div>
                  <label className={`block text-sm font-medium mb-1 ${themeIsDarkMode ? 'text-zinc-300' : 'text-gray-700'}`}>
                    Access Code
                  </label>
                  <input
                    type="text"
                    value={formData.access_code}
                    onChange={(e) => setFormData({ ...formData, access_code: e.target.value })}
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${styles.input}`}
                    placeholder="Enter access code"
                    required
                  />
                </div>
              )}

              {/* Media Settings */}
              <div className="space-y-2">
                <label className={`block text-sm font-medium ${themeIsDarkMode ? 'text-zinc-300' : 'text-gray-700'}`}>
                  Media Settings
                </label>
                <label className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${styles.card} ${themeIsDarkMode ? 'hover:bg-zinc-700' : 'hover:bg-gray-100'}`}>
                  <span className={`text-sm ${styles.text}`}>Voice enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.voice_enabled}
                    onChange={(e) => setFormData({ ...formData, voice_enabled: e.target.checked })}
                    className={themeIsDarkMode ? 'rounded text-cyan-400 focus:ring-cyan-400' : 'rounded text-purple-600 focus:ring-purple-500'}
                  />
                </label>
                <label className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${styles.card} ${themeIsDarkMode ? 'hover:bg-zinc-700' : 'hover:bg-gray-100'}`}>
                  <span className={`text-sm ${styles.text}`}>Video enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.video_enabled}
                    onChange={(e) => setFormData({ ...formData, video_enabled: e.target.checked })}
                    className={themeIsDarkMode ? 'rounded text-cyan-400 focus:ring-cyan-400' : 'rounded text-purple-600 focus:ring-purple-500'}
                  />
                </label>
                <label className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${styles.card} ${themeIsDarkMode ? 'hover:bg-zinc-700' : 'hover:bg-gray-100'}`}>
                  <span className={`text-sm ${styles.text}`}>Photo enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.photo_enabled}
                    onChange={(e) => setFormData({ ...formData, photo_enabled: e.target.checked })}
                    className={themeIsDarkMode ? 'rounded text-cyan-400 focus:ring-cyan-400' : 'rounded text-purple-600 focus:ring-purple-500'}
                  />
                </label>
              </div>

              {/* Save Button */}
              <button
                type="submit"
                disabled={loading}
                className={`w-full px-4 py-3 rounded-lg font-semibold transition-colors ${
                  loading
                    ? (themeIsDarkMode ? 'bg-gray-600 cursor-not-allowed text-white' : 'bg-gray-400 cursor-not-allowed text-white')
                    : styles.button
                }`}
              >
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
            </form>
          )}
          </div>
      </SheetContent>
    </Sheet>
  );
}
