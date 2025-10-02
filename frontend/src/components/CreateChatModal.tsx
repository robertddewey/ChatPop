'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { chatApi } from '@/lib/api';
import { X } from 'lucide-react';

const FORM_STORAGE_KEY = 'create_chat_form_data';

interface CreateChatModalProps {
  onClose: () => void;
}

export default function CreateChatModal({ onClose }: CreateChatModalProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    access_mode: 'public' as 'public' | 'private',
    access_code: '',
    voice_enabled: false,
    video_enabled: false,
    photo_enabled: true,
  });

  // Restore form data from localStorage on mount and auto-submit if logged in
  useEffect(() => {
    const savedData = localStorage.getItem(FORM_STORAGE_KEY);
    const token = localStorage.getItem('auth_token');

    if (savedData && token) {
      try {
        const restored = JSON.parse(savedData);
        setFormData(restored);
        localStorage.removeItem(FORM_STORAGE_KEY);

        // Auto-submit the form
        (async () => {
          setLoading(true);
          try {
            const chatRoom = await chatApi.createChat(restored);
            router.push(`/chat/${chatRoom.code}`);
          } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to create chat room');
            setLoading(false);
          }
        })();
      } catch (e) {
        console.error('Failed to restore form data:', e);
        localStorage.removeItem(FORM_STORAGE_KEY);
      }
    }
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Check if user is logged in
      const token = localStorage.getItem('auth_token');
      if (!token) {
        // Save form data before redirecting to login
        localStorage.setItem(FORM_STORAGE_KEY, JSON.stringify(formData));
        // Open login modal instead of redirecting
        const params = new URLSearchParams(window.location.search);
        params.set('auth', 'login');
        params.set('redirect', '/?modal=create');
        router.push(`/?${params.toString()}`);
        return;
      }

      const chatRoom = await chatApi.createChat(formData);

      // Clear any saved form data on success
      localStorage.removeItem(FORM_STORAGE_KEY);

      // Redirect to the chat room
      router.push(`/chat/${chatRoom.code}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create chat room');
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/20 backdrop-blur-sm">
      {/* Mobile: Full screen, Desktop: Max width */}
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl p-8 relative max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg transition-colors text-gray-400 hover:text-gray-600 hover:bg-gray-100"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          Room Settings
        </h1>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-600">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Chat Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-bold text-gray-700 mb-2">
              Group Chat Name (required)
            </label>
            <input
              type="text"
              id="name"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              placeholder=""
            />
          </div>

          {/* Access Mode */}
          <div>
            <label className="block text-sm font-bold text-gray-700 mb-2">
              Access Mode (required)
            </label>
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => setFormData({ ...formData, access_mode: 'public', access_code: '' })}
                className={`p-4 border-2 rounded-lg text-left transition-all ${
                  formData.access_mode === 'public'
                    ? 'border-purple-500 bg-purple-50'
                    : 'border-gray-300'
                }`}
              >
                <div className="font-semibold text-gray-900">Public</div>
                <div className="text-sm text-gray-600">Anyone with the link can join</div>
              </button>
              <button
                type="button"
                onClick={() => setFormData({ ...formData, access_mode: 'private' })}
                className={`p-4 border-2 rounded-lg text-left transition-all ${
                  formData.access_mode === 'private'
                    ? 'border-purple-500 bg-purple-50'
                    : 'border-gray-300'
                }`}
              >
                <div className="font-semibold text-gray-900">Private</div>
                <div className="text-sm text-gray-600">Requires access code</div>
              </button>
            </div>
          </div>

          {/* Access Code (for private rooms) */}
          {formData.access_mode === 'private' && (
            <div>
              <label htmlFor="access_code" className="block text-sm font-bold text-gray-700 mb-2">
                Access Code (required)
              </label>
              <input
                type="text"
                id="access_code"
                required
                value={formData.access_code}
                onChange={(e) => setFormData({ ...formData, access_code: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                placeholder=""
              />
            </div>
          )}

          {/* Features */}
          <div>
            <label className="block text-sm font-bold text-gray-700 mb-3">
              Enable Features
            </label>
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.photo_enabled}
                  onChange={(e) => setFormData({ ...formData, photo_enabled: e.target.checked })}
                  className="w-5 h-5 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                />
                <span className="text-gray-700">Photo Sharing</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.voice_enabled}
                  onChange={(e) => setFormData({ ...formData, voice_enabled: e.target.checked })}
                  className="w-5 h-5 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                />
                <span className="text-gray-700">Voice Messages</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.video_enabled}
                  onChange={(e) => setFormData({ ...formData, video_enabled: e.target.checked })}
                  className="w-5 h-5 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                />
                <span className="text-gray-700">Video Messages</span>
              </label>
            </div>
          </div>

          {/* Submit Button */}
          <div className="pt-4">
            <button
              type="submit"
              disabled={loading}
              className="w-full px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating...' : 'Create Room'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
