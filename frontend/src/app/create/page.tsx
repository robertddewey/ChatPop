'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { chatApi } from '@/lib/api';
import Header from '@/components/Header';

const FORM_STORAGE_KEY = 'create_chat_form_data';

export default function CreateChatPage() {
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
        router.push('/login?redirect=/create');
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
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 dark:from-gray-900 dark:to-gray-800">
      <Header />

      {/* Main Content */}
      <main className="container mx-auto px-4 py-12 max-w-2xl">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Room Settings
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-8">
            Set up your group chat and start engaging with your audience
          </p>

          {error && (
            <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Chat Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Group Chat Name (required)
              </label>
              <input
                type="text"
                id="name"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                placeholder="e.g., Tech Talk Tuesday"
              />
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Description
              </label>
              <textarea
                id="description"
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                placeholder="What's this chat about?"
              />
            </div>

            {/* Access Mode */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Access Mode (required)
              </label>
              <div className="grid grid-cols-2 gap-4">
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, access_mode: 'public', access_code: '' })}
                  className={`p-4 border-2 rounded-lg text-left transition-all ${
                    formData.access_mode === 'public'
                      ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                      : 'border-gray-300 dark:border-gray-600'
                  }`}
                >
                  <div className="font-semibold text-gray-900 dark:text-white">Public</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Anyone with the link can join</div>
                </button>
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, access_mode: 'private' })}
                  className={`p-4 border-2 rounded-lg text-left transition-all ${
                    formData.access_mode === 'private'
                      ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                      : 'border-gray-300 dark:border-gray-600'
                  }`}
                >
                  <div className="font-semibold text-gray-900 dark:text-white">Private</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Requires access code</div>
                </button>
              </div>
            </div>

            {/* Access Code (for private rooms) */}
            {formData.access_mode === 'private' && (
              <div>
                <label htmlFor="access_code" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Access Code (required)
                </label>
                <input
                  type="text"
                  id="access_code"
                  required
                  value={formData.access_code}
                  onChange={(e) => setFormData({ ...formData, access_code: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                  placeholder="e.g., VIP2024"
                />
              </div>
            )}

            {/* Features */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
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
                  <span className="text-gray-700 dark:text-gray-300">Photo Sharing</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.voice_enabled}
                    onChange={(e) => setFormData({ ...formData, voice_enabled: e.target.checked })}
                    className="w-5 h-5 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                  />
                  <span className="text-gray-700 dark:text-gray-300">Voice Messages</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.video_enabled}
                    onChange={(e) => setFormData({ ...formData, video_enabled: e.target.checked })}
                    className="w-5 h-5 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                  />
                  <span className="text-gray-700 dark:text-gray-300">Video Messages</span>
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
                {loading ? 'Creating...' : 'Start your ChatPop'}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
