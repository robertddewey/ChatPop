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
import { Copy, Check } from 'lucide-react';
import { migrateLegacyTheme, isDarkTheme, DEFAULT_THEME, type ThemeId } from '@/lib/themes';

interface ChatSettingsSheetProps {
  chatRoom: ChatRoom;
  currentUserId?: string;
  onUpdate?: (chatRoom: ChatRoom) => void;
  onThemeChange?: (theme: ThemeId) => void;
  children: React.ReactNode;
}

export default function ChatSettingsSheet({
  chatRoom,
  currentUserId,
  onUpdate,
  onThemeChange,
  children,
}: ChatSettingsSheetProps) {
  const router = useRouter();
  const isHost = chatRoom.host.id === currentUserId;
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

  // Get current theme directly from URL - only on client side
  const [currentTheme, setCurrentTheme] = useState<ThemeId>(() => {
    if (typeof window === 'undefined') return DEFAULT_THEME;
    const params = new URLSearchParams(window.location.search);
    return migrateLegacyTheme(params.get('design'));
  });

  useEffect(() => {
    // Update when sheet opens to ensure it's fresh
    if (isOpen) {
      const params = new URLSearchParams(window.location.search);
      const theme = migrateLegacyTheme(params.get('design'));
      setCurrentTheme(theme);
    }
  }, [isOpen]);

  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetTrigger asChild>{children}</SheetTrigger>
      <SheetContent
        side="bottom"
        className={`h-[100dvh] overflow-y-auto pt-2 ${
          isDarkTheme(currentTheme)
            ? 'bg-zinc-900 border-t-zinc-800'
            : 'bg-white border-t-white'
        }`}
        closeButtonClassName={isDarkTheme(currentTheme) ? 'text-white' : 'text-gray-900'}
      >
        <div className={isDarkTheme(currentTheme) ? 'dark' : ''}>
          <SheetHeader>
            <SheetTitle className={isDarkTheme(currentTheme) ? 'text-white' : ''}>
              Chat Settings
            </SheetTitle>
            <SheetDescription className={isDarkTheme(currentTheme) ? 'text-gray-400' : ''}>
              {isHost ? 'Manage your chat room settings' : 'Chat room information'}
            </SheetDescription>
          </SheetHeader>

          <div className="mt-6 space-y-6">
          {/* Theme Selection */}
          <div className="space-y-4">
            <h3 className={`text-sm font-semibold ${
              isDarkTheme(currentTheme) ? 'text-white' : 'text-gray-900'
            }`}>
              Theme
            </h3>

            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={() => {
                  const url = new URL(window.location.href);
                  url.searchParams.set('design', 'purple-dream');
                  router.replace(url.pathname + url.search, { scroll: false });
                  setCurrentTheme('purple-dream');
                  onThemeChange?.('purple-dream');
                }}
                className={`p-3 rounded-lg border-2 transition-all focus:outline-none ${
                  currentTheme === 'purple-dream'
                    ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                    : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800'
                }`}
              >
                <div className="text-xs font-semibold text-gray-900 dark:text-white mb-2">Purple Dream</div>
                <div className="h-8 rounded bg-gradient-to-r from-purple-500 via-pink-500 to-red-500"></div>
              </button>

              <button
                onClick={() => {
                  const url = new URL(window.location.href);
                  url.searchParams.set('design', 'ocean-blue');
                  router.replace(url.pathname + url.search, { scroll: false });
                  setCurrentTheme('ocean-blue');
                  onThemeChange?.('ocean-blue');
                }}
                className={`p-3 rounded-lg border-2 transition-all focus:outline-none ${
                  currentTheme === 'ocean-blue'
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800'
                }`}
              >
                <div className="text-xs font-semibold text-gray-900 dark:text-white mb-2">Ocean Blue</div>
                <div className="h-8 rounded bg-gradient-to-r from-blue-500 via-sky-500 to-cyan-500"></div>
              </button>

              <button
                onClick={() => {
                  const url = new URL(window.location.href);
                  url.searchParams.set('design', 'dark-mode');
                  router.replace(url.pathname + url.search, { scroll: false });
                  setCurrentTheme('dark-mode');
                  onThemeChange?.('dark-mode');
                }}
                className={`p-3 rounded-lg border-2 transition-all focus:outline-none ${
                  isDarkTheme(currentTheme)
                    ? 'border-cyan-400 bg-zinc-900'
                    : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800'
                }`}
              >
                <div className={`text-xs font-semibold mb-2 ${
                  isDarkTheme(currentTheme) ? 'text-zinc-100' : 'text-gray-900 dark:text-white'
                }`}>Dark Mode</div>
                <div className="h-8 rounded bg-zinc-950 flex items-center justify-center gap-1">
                  <div className="h-4 w-12 rounded bg-cyan-400"></div>
                  <div className="h-4 w-8 rounded bg-yellow-400"></div>
                </div>
              </button>
            </div>
          </div>

          {/* Chat Information for All Users */}
          <div className={`space-y-4 pt-4 border-t ${
            isDarkTheme(currentTheme) ? 'border-zinc-700' : 'border-gray-200'
          }`}>
            <h3 className={`text-sm font-semibold ${
              isDarkTheme(currentTheme) ? 'text-white' : 'text-gray-900'
            }`}>
              Chat Information
            </h3>

            {/* Chat Name */}
            <div className={`p-3 rounded-lg ${
              isDarkTheme(currentTheme) ? 'bg-zinc-800' : 'bg-gray-50'
            }`}>
              <p className={`text-xs ${isDarkTheme(currentTheme) ? 'text-gray-400' : 'text-gray-500'}`}>Chat Name</p>
              <p className={`text-sm font-semibold ${isDarkTheme(currentTheme) ? 'text-white' : 'text-black'}`}>
                {chatRoom.name}
              </p>
            </div>

            {/* Chat Code */}
            <div className={`flex items-center justify-between p-3 rounded-lg ${
              isDarkTheme(currentTheme) ? 'bg-zinc-800' : 'bg-gray-50'
            }`}>
              <div>
                <p className={`text-xs ${isDarkTheme(currentTheme) ? 'text-gray-400' : 'text-gray-500'}`}>Chat Code</p>
                <p className={`text-sm font-mono font-semibold ${isDarkTheme(currentTheme) ? 'text-white' : 'text-black'}`}>{chatRoom.code}</p>
              </div>
              <button
                onClick={handleCopyCode}
                className="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                {copiedCode ? (
                  <Check className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
            </div>

            {/* Share Link */}
            <div className={`flex items-center justify-between p-3 rounded-lg ${
              isDarkTheme(currentTheme) ? 'bg-zinc-800' : 'bg-gray-50'
            }`}>
              <div className="flex-1 min-w-0">
                <p className={`text-xs ${isDarkTheme(currentTheme) ? 'text-gray-400' : 'text-gray-500'}`}>Share Link</p>
                <p className={`text-sm font-mono truncate ${isDarkTheme(currentTheme) ? 'text-white' : 'text-black'}`}>{shareLink}</p>
              </div>
              <button
                onClick={handleCopyLink}
                className="ml-2 p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors flex-shrink-0"
              >
                {copiedLink ? (
                  <Check className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
            </div>

            {/* Host Info */}
            <div className={`p-3 rounded-lg ${
              isDarkTheme(currentTheme) ? 'bg-zinc-800' : 'bg-gray-50'
            }`}>
              <p className={`text-xs ${isDarkTheme(currentTheme) ? 'text-gray-400' : 'text-gray-500'}`}>Hosted by</p>
              <p className={`text-sm font-semibold ${isDarkTheme(currentTheme) ? 'text-white' : 'text-black'}`}>
                {chatRoom.host.display_name || chatRoom.host.email}
              </p>
            </div>

            {/* Created Date */}
            <div className={`p-3 rounded-lg ${
              isDarkTheme(currentTheme) ? 'bg-zinc-800' : 'bg-gray-50'
            }`}>
              <p className={`text-xs ${isDarkTheme(currentTheme) ? 'text-gray-400' : 'text-gray-500'}`}>Created</p>
              <p className={`text-sm ${isDarkTheme(currentTheme) ? 'text-white' : 'text-black'}`}>
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
            <form onSubmit={handleSubmit} className={`space-y-4 pt-4 border-t ${
              isDarkTheme(currentTheme) ? 'border-zinc-700' : 'border-gray-200'
            }`}>
              <h3 className={`text-sm font-semibold ${
                isDarkTheme(currentTheme) ? 'text-white' : 'text-gray-900'
              }`}>
                Edit Settings (Host Only)
              </h3>

              {error && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-600 dark:text-red-400">
                  {error}
                </div>
              )}

              {success && (
                <div className="p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-600 dark:text-green-400">
                  {success}
                </div>
              )}

              {/* Chat Name */}
              <div>
                <label className={`block text-sm font-medium mb-1 ${
                  isDarkTheme(currentTheme) ? 'text-zinc-300' : 'text-gray-700'
                }`}>
                  Chat Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${
                    isDarkTheme(currentTheme)
                      ? 'bg-zinc-800 border-zinc-700 text-zinc-100 focus:ring-cyan-400'
                      : 'bg-white border-gray-300 text-gray-900 focus:ring-purple-500'
                  }`}
                  required
                />
              </div>

              {/* Access Mode */}
              <div>
                <label className={`block text-sm font-medium mb-2 ${
                  isDarkTheme(currentTheme) ? 'text-zinc-300' : 'text-gray-700'
                }`}>
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
                      className={`mr-2 ${
                        isDarkTheme(currentTheme)
                          ? 'text-cyan-400 focus:ring-cyan-400'
                          : 'text-purple-600 focus:ring-purple-500'
                      }`}
                    />
                    <span className={`text-sm ${
                      isDarkTheme(currentTheme) ? 'text-zinc-100' : 'text-gray-900'
                    }`}>Public</span>
                  </label>
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="radio"
                      value="private"
                      checked={formData.access_mode === 'private'}
                      onChange={(e) =>
                        setFormData({ ...formData, access_mode: e.target.value as 'public' | 'private' })
                      }
                      className={`mr-2 ${
                        isDarkTheme(currentTheme)
                          ? 'text-cyan-400 focus:ring-cyan-400'
                          : 'text-purple-600 focus:ring-purple-500'
                      }`}
                    />
                    <span className={`text-sm ${
                      isDarkTheme(currentTheme) ? 'text-zinc-100' : 'text-gray-900'
                    }`}>Private</span>
                  </label>
                </div>
              </div>

              {/* Access Code (if private) */}
              {formData.access_mode === 'private' && (
                <div>
                  <label className={`block text-sm font-medium mb-1 ${
                    isDarkTheme(currentTheme) ? 'text-zinc-300' : 'text-gray-700'
                  }`}>
                    Access Code
                  </label>
                  <input
                    type="text"
                    value={formData.access_code}
                    onChange={(e) => setFormData({ ...formData, access_code: e.target.value })}
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${
                      isDarkTheme(currentTheme)
                        ? 'bg-zinc-800 border-zinc-700 text-zinc-100 focus:ring-cyan-400'
                        : 'bg-white border-gray-300 text-gray-900 focus:ring-purple-500'
                    }`}
                    placeholder="Enter access code"
                    required
                  />
                </div>
              )}

              {/* Media Settings */}
              <div className="space-y-2">
                <label className={`block text-sm font-medium ${
                  isDarkTheme(currentTheme) ? 'text-zinc-300' : 'text-gray-700'
                }`}>
                  Media Settings
                </label>
                <label className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                  isDarkTheme(currentTheme)
                    ? 'bg-zinc-800 hover:bg-zinc-700'
                    : 'bg-gray-50 hover:bg-gray-100'
                }`}>
                  <span className={`text-sm ${
                    isDarkTheme(currentTheme) ? 'text-zinc-100' : 'text-gray-900'
                  }`}>Voice enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.voice_enabled}
                    onChange={(e) => setFormData({ ...formData, voice_enabled: e.target.checked })}
                    className={`rounded ${
                      isDarkTheme(currentTheme)
                        ? 'text-cyan-400 focus:ring-cyan-400'
                        : 'text-purple-600 focus:ring-purple-500'
                    }`}
                  />
                </label>
                <label className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                  isDarkTheme(currentTheme)
                    ? 'bg-zinc-800 hover:bg-zinc-700'
                    : 'bg-gray-50 hover:bg-gray-100'
                }`}>
                  <span className={`text-sm ${
                    isDarkTheme(currentTheme) ? 'text-zinc-100' : 'text-gray-900'
                  }`}>Video enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.video_enabled}
                    onChange={(e) => setFormData({ ...formData, video_enabled: e.target.checked })}
                    className={`rounded ${
                      isDarkTheme(currentTheme)
                        ? 'text-cyan-400 focus:ring-cyan-400'
                        : 'text-purple-600 focus:ring-purple-500'
                    }`}
                  />
                </label>
                <label className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                  isDarkTheme(currentTheme)
                    ? 'bg-zinc-800 hover:bg-zinc-700'
                    : 'bg-gray-50 hover:bg-gray-100'
                }`}>
                  <span className={`text-sm ${
                    isDarkTheme(currentTheme) ? 'text-zinc-100' : 'text-gray-900'
                  }`}>Photo enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.photo_enabled}
                    onChange={(e) => setFormData({ ...formData, photo_enabled: e.target.checked })}
                    className={`rounded ${
                      isDarkTheme(currentTheme)
                        ? 'text-cyan-400 focus:ring-cyan-400'
                        : 'text-purple-600 focus:ring-purple-500'
                    }`}
                  />
                </label>
              </div>

              {/* Save Button */}
              <button
                type="submit"
                disabled={loading}
                className={`w-full px-4 py-3 rounded-lg font-semibold transition-colors ${
                  loading
                    ? 'bg-gray-400 cursor-not-allowed'
                    : isDarkTheme(currentTheme)
                    ? 'bg-cyan-400 hover:bg-cyan-500 text-cyan-950'
                    : 'bg-purple-600 hover:bg-purple-700 text-white'
                }`}
              >
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
            </form>
          )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
