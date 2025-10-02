'use client';

import React, { useState, useEffect } from 'react';
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

interface ChatSettingsSheetProps {
  chatRoom: ChatRoom;
  currentUserId?: string;
  onUpdate?: (chatRoom: ChatRoom) => void;
  children: React.ReactNode;
}

export default function ChatSettingsSheet({
  chatRoom,
  currentUserId,
  onUpdate,
  children,
}: ChatSettingsSheetProps) {
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

  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetTrigger asChild>{children}</SheetTrigger>
      <SheetContent side="bottom" className="h-[100dvh] overflow-y-auto pt-2 border-t-white dark:border-t-gray-950">
        <SheetHeader>
          <SheetTitle>Chat Settings</SheetTitle>
          <SheetDescription>
            {isHost ? 'Manage your chat room settings' : 'Chat room information'}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Back Room Section */}
          {chatRoom.has_back_room && backRoom && (
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                Back Room
              </h3>

              <div className="space-y-2">
                <div className="flex justify-between p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    Price per seat
                  </span>
                  <span className="text-sm font-semibold">${backRoom.price_per_seat}</span>
                </div>

                <div className="flex justify-between p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    Seats available
                  </span>
                  <span className="text-sm font-semibold">
                    {backRoom.seats_available} / {backRoom.max_seats}
                  </span>
                </div>

                {!isHost && backRoom.is_active && !backRoom.is_full && (
                  <button className="w-full mt-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-semibold transition-colors">
                    Join Back Room - ${backRoom.price_per_seat}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Chat Information for All Users */}
          <div className="space-y-4 pt-4 border-t dark:border-gray-700">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
              Chat Information
            </h3>

            {/* Chat Code */}
            <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">Chat Code</p>
                <p className="text-sm font-mono font-semibold">{chatRoom.code}</p>
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
            <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-500 dark:text-gray-400">Share Link</p>
                <p className="text-sm font-mono truncate">{shareLink}</p>
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
            <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <p className="text-xs text-gray-500 dark:text-gray-400">Hosted by</p>
              <p className="text-sm font-semibold">
                {chatRoom.host.display_name || chatRoom.host.email}
              </p>
            </div>

            {/* Created Date */}
            <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <p className="text-xs text-gray-500 dark:text-gray-400">Created</p>
              <p className="text-sm">
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
            <form onSubmit={handleSubmit} className="space-y-4 pt-4 border-t dark:border-gray-700">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
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
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Chat Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  required
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Description
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>

              {/* Access Mode */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Access Mode
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="public"
                      checked={formData.access_mode === 'public'}
                      onChange={(e) =>
                        setFormData({ ...formData, access_mode: e.target.value as 'public' | 'private' })
                      }
                      className="mr-2"
                    />
                    <span className="text-sm">Public</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="private"
                      checked={formData.access_mode === 'private'}
                      onChange={(e) =>
                        setFormData({ ...formData, access_mode: e.target.value as 'public' | 'private' })
                      }
                      className="mr-2"
                    />
                    <span className="text-sm">Private</span>
                  </label>
                </div>
              </div>

              {/* Access Code (if private) */}
              {formData.access_mode === 'private' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Access Code
                  </label>
                  <input
                    type="text"
                    value={formData.access_code}
                    onChange={(e) => setFormData({ ...formData, access_code: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    placeholder="Enter access code"
                    required
                  />
                </div>
              )}

              {/* Media Settings */}
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Media Settings
                </label>
                <label className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
                  <span className="text-sm">Voice enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.voice_enabled}
                    onChange={(e) => setFormData({ ...formData, voice_enabled: e.target.checked })}
                    className="rounded"
                  />
                </label>
                <label className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
                  <span className="text-sm">Video enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.video_enabled}
                    onChange={(e) => setFormData({ ...formData, video_enabled: e.target.checked })}
                    className="rounded"
                  />
                </label>
                <label className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
                  <span className="text-sm">Photo enabled</span>
                  <input
                    type="checkbox"
                    checked={formData.photo_enabled}
                    onChange={(e) => setFormData({ ...formData, photo_enabled: e.target.checked })}
                    className="rounded"
                  />
                </label>
              </div>

              {/* Save Button */}
              <button
                type="submit"
                disabled={loading}
                className="w-full px-4 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white rounded-lg font-semibold transition-colors"
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
