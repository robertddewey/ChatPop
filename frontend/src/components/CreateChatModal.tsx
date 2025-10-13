'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { chatApi } from '@/lib/api';
import { X } from 'lucide-react';

const FORM_STORAGE_KEY = 'create_chat_form_data';

interface CreateChatModalProps {
  onClose: () => void;
}

export default function CreateChatModal({ onClose }: CreateChatModalProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
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

  // Prevent body scrolling when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  // Restore form data from localStorage on mount and auto-submit if logged in
  useEffect(() => {
    const savedData = localStorage.getItem(FORM_STORAGE_KEY);
    const token = localStorage.getItem('auth_token');

    console.log('[CreateChatModal] Restore effect:', {
      hasSavedData: !!savedData,
      hasToken: !!token,
      savedDataContent: savedData,
      tokenPreview: token?.substring(0, 10) + '...'
    });

    if (savedData && token) {
      try {
        const restored = JSON.parse(savedData);
        console.log('[CreateChatModal] Restored data:', restored);
        setFormData(restored);

        // Only auto-submit if the form has a name (meaning user actually filled it out)
        if (restored.name && restored.name.trim()) {
          console.log('[CreateChatModal] Auto-submitting chat creation...');
          (async () => {
            setLoading(true);
            try {
              const chatRoom = await chatApi.createChat(restored);
              console.log('[CreateChatModal] Chat created successfully:', chatRoom);
              // Clear saved form data AFTER successful creation
              localStorage.removeItem(FORM_STORAGE_KEY);
              router.push(`/chat/${chatRoom.code}`);
            } catch (err: any) {
              console.error('[CreateChatModal] Failed to create chat:', err);
              setError(err.response?.data?.detail || 'Failed to create chat room');
              setLoading(false);
            }
          })();
        } else {
          console.log('[CreateChatModal] Skipping auto-submit - no chat name');
          // Clear empty form data
          localStorage.removeItem(FORM_STORAGE_KEY);
        }
      } catch (e) {
        console.error('Failed to restore form data:', e);
        localStorage.removeItem(FORM_STORAGE_KEY);
      }
    }
  }, [router, searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    console.log('[CreateChatModal] Form submitted:', formData);
    setError('');
    setLoading(true);

    try {
      // Check if user is logged in
      const token = localStorage.getItem('auth_token');
      console.log('[CreateChatModal] Has auth token:', !!token);

      if (!token) {
        // Save form data before redirecting to login
        console.log('[CreateChatModal] No token, saving form data and redirecting to auth');
        localStorage.setItem(FORM_STORAGE_KEY, JSON.stringify(formData));
        // Open login modal instead of redirecting
        const params = new URLSearchParams(window.location.search);
        params.set('auth', 'login');
        params.set('redirect', '/?modal=create');
        router.push(`/?${params.toString()}`);
        return;
      }

      console.log('[CreateChatModal] Creating chat room...');
      const chatRoom = await chatApi.createChat(formData);
      console.log('[CreateChatModal] Chat room created:', chatRoom);

      // Clear any saved form data on success
      localStorage.removeItem(FORM_STORAGE_KEY);

      // Redirect to the chat room
      router.push(`/chat/${chatRoom.code}`);
    } catch (err: any) {
      console.error('[CreateChatModal] Error creating chat room:', err);
      setError(err.response?.data?.detail || 'Failed to create chat room');
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      {/* Mobile: Full screen, Desktop: Max width */}
      <div className="w-full max-w-lg bg-zinc-800 border border-zinc-700 rounded-2xl shadow-xl p-8 relative max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg transition-colors text-zinc-300 hover:text-zinc-100 hover:bg-zinc-700 cursor-pointer"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <h1 className="text-3xl font-bold text-zinc-50 mb-4">
          Room Settings
        </h1>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/20 border border-red-800 rounded-lg text-red-400">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Chat Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-bold text-zinc-200 mb-2">
              Group Chat Name (required)
            </label>
            <input
              type="text"
              id="name"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-4 py-3 border border-zinc-600 rounded-xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 transition-colors focus:outline-none bg-zinc-700 text-zinc-50 placeholder-zinc-400"
              placeholder=""
            />
          </div>

          {/* Access Mode */}
          <div>
            <label className="block text-sm font-bold text-zinc-200 mb-2">
              Access Mode (required)
            </label>
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => setFormData({ ...formData, access_mode: 'public', access_code: '' })}
                className={`p-4 border-2 rounded-lg text-left transition-all cursor-pointer ${
                  formData.access_mode === 'public'
                    ? 'border-cyan-400 bg-cyan-900/20'
                    : 'border-zinc-600'
                }`}
              >
                <div className="font-semibold text-zinc-50">Public</div>
                <div className="text-sm text-zinc-300">Anyone with the link can join</div>
              </button>
              <button
                type="button"
                onClick={() => setFormData({ ...formData, access_mode: 'private' })}
                className={`p-4 border-2 rounded-lg text-left transition-all cursor-pointer ${
                  formData.access_mode === 'private'
                    ? 'border-cyan-400 bg-cyan-900/20'
                    : 'border-zinc-600'
                }`}
              >
                <div className="font-semibold text-zinc-50">Private</div>
                <div className="text-sm text-zinc-300">Requires access code</div>
              </button>
            </div>
          </div>

          {/* Access Code (for private rooms) */}
          {formData.access_mode === 'private' && (
            <div>
              <label htmlFor="access_code" className="block text-sm font-bold text-zinc-200 mb-2">
                Access Code (required)
              </label>
              <input
                type="text"
                id="access_code"
                required
                value={formData.access_code}
                onChange={(e) => setFormData({ ...formData, access_code: e.target.value })}
                className="w-full px-4 py-3 border border-zinc-600 rounded-xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 transition-colors focus:outline-none bg-zinc-700 text-zinc-50 placeholder-zinc-400"
                placeholder=""
              />
            </div>
          )}

          {/* Features */}
          <div>
            <label className="block text-sm font-bold text-zinc-200 mb-3">
              Enable Features
            </label>
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.photo_enabled}
                  onChange={(e) => setFormData({ ...formData, photo_enabled: e.target.checked })}
                  className="w-5 h-5 text-cyan-400 border-zinc-600 rounded focus:ring-cyan-400"
                />
                <span className="text-zinc-200">Photo Sharing</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.voice_enabled}
                  onChange={(e) => setFormData({ ...formData, voice_enabled: e.target.checked })}
                  className="w-5 h-5 text-cyan-400 border-zinc-600 rounded focus:ring-cyan-400"
                />
                <span className="text-zinc-200">Voice Messages</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.video_enabled}
                  onChange={(e) => setFormData({ ...formData, video_enabled: e.target.checked })}
                  className="w-5 h-5 text-cyan-400 border-zinc-600 rounded focus:ring-cyan-400"
                />
                <span className="text-zinc-200">Video Messages</span>
              </label>
            </div>
          </div>

          {/* Submit Button */}
          <div className="pt-4">
            <button
              type="submit"
              disabled={loading}
              className="w-full px-6 py-3 bg-[#404eed] text-white font-semibold rounded-lg hover:bg-[#3640d9] transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {loading ? 'Creating...' : 'Create Room'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
