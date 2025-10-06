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
import { chatApi, backRoomApi, type ChatRoom, type BackRoom } from '@/lib/api';
import { Copy, Check, BadgeCheck, Sun, Moon, Smartphone } from 'lucide-react';
import { migrateLegacyTheme, DEFAULT_THEME, type ThemeId, isDarkTheme } from '@/lib/themes';

interface ChatSettingsSheetProps {
  chatRoom: ChatRoom;
  currentUserId?: string;
  onUpdate?: (chatRoom: ChatRoom) => void;
  onThemeChange?: (theme: ThemeId) => void;
  design?: 'pink-dream' | 'ocean-blue' | 'dark-mode';
  children: React.ReactNode;
}

export default function ChatSettingsSheet({
  chatRoom,
  currentUserId,
  onUpdate,
  onThemeChange,
  design = 'pink-dream',
  children,
}: ChatSettingsSheetProps) {
  const router = useRouter();
  const isHost = chatRoom.host.id === currentUserId;
  const useDarkMode = isDarkTheme(design);

  // Theme-aware styles
  const styles = useDarkMode ? {
    title: 'text-white',
    subtitle: 'text-zinc-400',
    text: 'text-white',
    subtext: 'text-gray-400',
    input: 'bg-zinc-800 border-zinc-700 text-zinc-100 focus:ring-cyan-400',
    card: 'bg-zinc-800',
    button: 'bg-cyan-400 hover:bg-cyan-500 text-cyan-950',
    border: 'border-zinc-700',
  } : {
    title: 'text-gray-900 dark:text-white',
    subtitle: 'text-gray-600 dark:text-zinc-400',
    text: 'text-black dark:text-white',
    subtext: 'text-gray-500 dark:text-gray-400',
    input: 'bg-white dark:bg-zinc-800 border-gray-300 dark:border-zinc-700 text-gray-900 dark:text-zinc-100 focus:ring-purple-500 dark:focus:ring-cyan-400',
    card: 'bg-gray-50 dark:bg-zinc-800',
    button: 'bg-purple-600 dark:bg-cyan-400 hover:bg-purple-700 dark:hover:bg-cyan-500 text-white dark:text-cyan-950',
    border: 'border-gray-200 dark:border-zinc-700',
  };

  // Theme card styles with explicit border colors for better visibility
  const getThemeCardStyles = (themeId: ThemeId) => {
    const isSelected = currentTheme === themeId;

    if (useDarkMode) {
      // Dark Mode theme - use bright borders for visibility
      if (themeId === 'pink-dream') {
        return isSelected
          ? 'border-2 border-purple-400 bg-purple-900/20'
          : 'border-2 border-gray-600 bg-gray-800';
      } else if (themeId === 'ocean-blue') {
        return isSelected
          ? 'border-2 border-blue-400 bg-blue-900/20'
          : 'border-2 border-gray-600 bg-gray-800';
      } else if (themeId === 'dark-mode') {
        return isSelected
          ? 'border-2 border-cyan-400 bg-cyan-900/20'
          : 'border-2 border-gray-600 bg-gray-800';
      }
    } else {
      // Light themes - adapt to system mode
      if (themeId === 'pink-dream') {
        return isSelected
          ? 'border-2 border-purple-500 bg-purple-50 dark:bg-purple-900/20'
          : 'border-2 border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800';
      } else if (themeId === 'ocean-blue') {
        return isSelected
          ? 'border-2 border-blue-500 bg-blue-50 dark:bg-blue-900/20'
          : 'border-2 border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800';
      } else if (themeId === 'dark-mode') {
        return isSelected
          ? 'border-2 border-cyan-500 bg-cyan-50 dark:bg-cyan-900/20'
          : 'border-2 border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800';
      }
    }

    // Fallback
    return 'border-2 border-gray-300 bg-white';
  };

  const [isOpen, setIsOpen] = useState(false);
  const [backRoom, setBackRoom] = useState<BackRoom | null>(null);
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

  // Load back room info if available
  useEffect(() => {
    if (isOpen && chatRoom.has_back_room) {
      loadBackRoom();
    }
  }, [isOpen, chatRoom.has_back_room]);

  const loadBackRoom = async () => {
    try {
      const br = await backRoomApi.getBackRoom(chatRoom.code);
      setBackRoom(br);
    } catch (err) {
      console.error('Failed to load back room:', err);
    }
  };

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

  // Get current theme from localStorage (matching page.tsx logic)
  const [currentTheme, setCurrentTheme] = useState<ThemeId>(DEFAULT_THEME);

  useEffect(() => {
    // Update when sheet opens to ensure it's fresh
    if (isOpen) {
      // Priority 1: URL parameter
      const params = new URLSearchParams(window.location.search);
      const urlTheme = params.get('design');
      if (urlTheme && ['pink-dream', 'ocean-blue', 'dark-mode'].includes(urlTheme)) {
        setCurrentTheme(urlTheme as ThemeId);
        return;
      }

      // Priority 2: localStorage
      const localTheme = localStorage.getItem(`chatpop_theme_${chatRoom.code}`);
      if (localTheme && ['pink-dream', 'ocean-blue', 'dark-mode'].includes(localTheme)) {
        setCurrentTheme(localTheme as ThemeId);
        return;
      }

      // Fallback to default
      setCurrentTheme(DEFAULT_THEME);
    }
  }, [isOpen, chatRoom.code]);

  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetTrigger asChild>{children}</SheetTrigger>
      <SheetContent
        side="bottom"
        className={`h-[100dvh] overflow-y-auto pt-2 ${
          useDarkMode
            ? 'bg-zinc-900 border-t-zinc-800'
            : 'bg-white dark:bg-zinc-900 border-t-white dark:border-t-zinc-800'
        }`}
        closeButtonClassName={useDarkMode ? 'text-white' : 'text-gray-900 dark:text-white'}
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
              Theme <span className={`text-xs font-normal ${styles.subtext}`}>(chat will reload)</span>
            </h3>

            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={() => {
                  // Extract chat code from URL
                  const match = window.location.pathname.match(/\/chat\/([^\/]+)/);
                  if (match) {
                    const code = match[1];
                    localStorage.setItem('chatpop_theme_' + code, 'pink-dream');
                  }
                  // Remove design parameter from URL and reload
                  const url = new URL(window.location.href);
                  url.searchParams.delete('design');
                  window.location.href = url.pathname + url.search;
                }}
                className={`p-3 rounded-lg transition-all focus:outline-none ${getThemeCardStyles('pink-dream')}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className={`text-xs font-semibold ${styles.text}`}>Pink Dream</div>
                  <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] ${useDarkMode ? 'bg-zinc-800 text-zinc-400' : 'bg-gray-100 dark:bg-zinc-800 text-gray-600 dark:text-zinc-400'}`}>
                    <Smartphone size={10} />
                    <span>Auto</span>
                  </div>
                </div>
                <div className="h-8 rounded bg-gradient-to-r from-purple-500 via-pink-500 to-red-500"></div>
              </button>

              <button
                onClick={() => {
                  // Extract chat code from URL
                  const match = window.location.pathname.match(/\/chat\/([^\/]+)/);
                  if (match) {
                    const code = match[1];
                    localStorage.setItem('chatpop_theme_' + code, 'ocean-blue');
                  }
                  // Remove design parameter from URL and reload
                  const url = new URL(window.location.href);
                  url.searchParams.delete('design');
                  window.location.href = url.pathname + url.search;
                }}
                className={`p-3 rounded-lg transition-all focus:outline-none ${getThemeCardStyles('ocean-blue')}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className={`text-xs font-semibold ${styles.text}`}>Ocean Blue</div>
                  <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] ${useDarkMode ? 'bg-zinc-800 text-zinc-400' : 'bg-gray-100 dark:bg-zinc-800 text-gray-600 dark:text-zinc-400'}`}>
                    <Smartphone size={10} />
                    <span>Auto</span>
                  </div>
                </div>
                <div className="h-8 rounded bg-gradient-to-r from-blue-500 via-sky-500 to-cyan-500"></div>
              </button>

              <button
                onClick={() => {
                  // Extract chat code from URL
                  const match = window.location.pathname.match(/\/chat\/([^\/]+)/);
                  if (match) {
                    const code = match[1];
                    localStorage.setItem('chatpop_theme_' + code, 'dark-mode');
                  }
                  // Remove design parameter from URL and reload
                  const url = new URL(window.location.href);
                  url.searchParams.delete('design');
                  window.location.href = url.pathname + url.search;
                }}
                className={`p-3 rounded-lg transition-all focus:outline-none ${getThemeCardStyles('dark-mode')}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className={`text-xs font-semibold ${styles.text}`}>Dark Mode</div>
                  <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] ${useDarkMode ? 'bg-zinc-800 text-zinc-400' : 'bg-gray-100 dark:bg-zinc-800 text-gray-600 dark:text-zinc-400'}`}>
                    <Moon size={10} />
                    <span>Dark</span>
                  </div>
                </div>
                <div className="h-8 rounded bg-zinc-950 flex items-center justify-center gap-1">
                  <div className="h-4 w-12 rounded bg-cyan-400"></div>
                  <div className="h-4 w-8 rounded bg-yellow-400"></div>
                </div>
              </button>
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
                className={`p-2 rounded-lg transition-colors ${useDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-200 dark:hover:bg-gray-700'}`}
              >
                {copiedCode ? (
                  <Check className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className={`w-4 h-4 ${useDarkMode ? 'text-gray-400' : 'text-gray-600 dark:text-gray-400'}`} />
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
                className={`ml-2 p-2 rounded-lg transition-colors flex-shrink-0 ${useDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-200 dark:hover:bg-gray-700'}`}
              >
                {copiedLink ? (
                  <Check className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className={`w-4 h-4 ${useDarkMode ? 'text-gray-400' : 'text-gray-600 dark:text-gray-400'}`} />
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
                <div className={`p-3 rounded-lg text-sm ${useDarkMode ? 'bg-red-900/20 border border-red-800 text-red-400' : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400'}`}>
                  {error}
                </div>
              )}

              {success && (
                <div className={`p-3 rounded-lg text-sm ${useDarkMode ? 'bg-green-900/20 border border-green-800 text-green-400' : 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-600 dark:text-green-400'}`}>
                  {success}
                </div>
              )}

              {/* Chat Name */}
              <div>
                <label className={`block text-sm font-medium mb-1 ${useDarkMode ? 'text-zinc-300' : 'text-gray-700 dark:text-zinc-300'}`}>
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
                <label className={`block text-sm font-medium mb-2 ${useDarkMode ? 'text-zinc-300' : 'text-gray-700 dark:text-zinc-300'}`}>
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
                      className={useDarkMode ? 'mr-2 text-cyan-400 focus:ring-cyan-400' : 'mr-2 text-purple-600 dark:text-cyan-400 focus:ring-purple-500 dark:focus:ring-cyan-400'}
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
                      className={useDarkMode ? 'mr-2 text-cyan-400 focus:ring-cyan-400' : 'mr-2 text-purple-600 dark:text-cyan-400 focus:ring-purple-500 dark:focus:ring-cyan-400'}
                    />
                    <span className={`text-sm ${styles.text}`}>Private</span>
                  </label>
                </div>
              </div>

              {/* Access Code (if private) */}
              {formData.access_mode === 'private' && (
                <div>
                  <label className={`block text-sm font-medium mb-1 ${useDarkMode ? 'text-zinc-300' : 'text-gray-700 dark:text-zinc-300'}`}>
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
                <label className={`block text-sm font-medium ${useDarkMode ? 'text-zinc-300' : 'text-gray-700 dark:text-zinc-300'}`}>
                  Media Settings
                </label>
                <label className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${styles.card} ${useDarkMode ? 'hover:bg-zinc-700' : 'hover:bg-gray-100 dark:hover:bg-zinc-700'}`}>
                  <span className={`text-sm ${styles.text}`}>Voice enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.voice_enabled}
                    onChange={(e) => setFormData({ ...formData, voice_enabled: e.target.checked })}
                    className={useDarkMode ? 'rounded text-cyan-400 focus:ring-cyan-400' : 'rounded text-purple-600 dark:text-cyan-400 focus:ring-purple-500 dark:focus:ring-cyan-400'}
                  />
                </label>
                <label className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${styles.card} ${useDarkMode ? 'hover:bg-zinc-700' : 'hover:bg-gray-100 dark:hover:bg-zinc-700'}`}>
                  <span className={`text-sm ${styles.text}`}>Video enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.video_enabled}
                    onChange={(e) => setFormData({ ...formData, video_enabled: e.target.checked })}
                    className={useDarkMode ? 'rounded text-cyan-400 focus:ring-cyan-400' : 'rounded text-purple-600 dark:text-cyan-400 focus:ring-purple-500 dark:focus:ring-cyan-400'}
                  />
                </label>
                <label className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${styles.card} ${useDarkMode ? 'hover:bg-zinc-700' : 'hover:bg-gray-100 dark:hover:bg-zinc-700'}`}>
                  <span className={`text-sm ${styles.text}`}>Photo enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.photo_enabled}
                    onChange={(e) => setFormData({ ...formData, photo_enabled: e.target.checked })}
                    className={useDarkMode ? 'rounded text-cyan-400 focus:ring-cyan-400' : 'rounded text-purple-600 dark:text-cyan-400 focus:ring-purple-500 dark:focus:ring-cyan-400'}
                  />
                </label>
              </div>

              {/* Save Button */}
              <button
                type="submit"
                disabled={loading}
                className={`w-full px-4 py-3 rounded-lg font-semibold transition-colors ${
                  loading
                    ? (useDarkMode ? 'bg-gray-600 cursor-not-allowed text-white' : 'bg-gray-400 dark:bg-gray-600 cursor-not-allowed text-white')
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
