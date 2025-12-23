'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { chatApi } from '@/lib/api';
import { X, MapPin, Loader2, Image, Mic, Video } from 'lucide-react';

const FORM_STORAGE_KEY = 'create_chat_form_data';

interface CreateChatModalProps {
  onClose: () => void;
}

interface LocationState {
  enabled: boolean;
  latitude: number | null;
  longitude: number | null;
  discovery_radius_miles: number;
  loading: boolean;
  error: string | null;
}

export default function CreateChatModal({ onClose }: CreateChatModalProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [radiusOptions, setRadiusOptions] = useState<number[]>([1, 5, 10, 25, 50]);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    access_mode: 'public' as 'public' | 'private',
    access_code: '',
    voice_enabled: false,
    video_enabled: false,
    photo_enabled: true,
  });
  const [location, setLocation] = useState<LocationState>({
    enabled: false,
    latitude: null,
    longitude: null,
    discovery_radius_miles: 1, // Default to 1 mile
    loading: false,
    error: null,
  });

  // Ref for scrollable content area
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom of content area
  const scrollToBottom = () => {
    setTimeout(() => {
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'smooth'
        });
      }
    }, 100); // Small delay to allow DOM to update
  };

  // Prevent body scrolling when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  // Fetch config options on mount
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const config = await chatApi.getConfig();
        setRadiusOptions(config.discovery_radius_options);
        // Set default to first option
        if (config.discovery_radius_options.length > 0) {
          setLocation(prev => ({ ...prev, discovery_radius_miles: config.discovery_radius_options[0] }));
        }
      } catch (err) {
        console.error('Failed to fetch chat config:', err);
      }
    };
    fetchConfig();
  }, []);

  // Handle enabling/disabling location discovery
  const handleLocationToggle = async (enabled: boolean) => {
    if (enabled) {
      // Request geolocation
      setLocation(prev => ({ ...prev, enabled: true, loading: true, error: null }));

      if (!navigator.geolocation) {
        setLocation(prev => ({
          ...prev,
          enabled: false,
          loading: false,
          error: 'Geolocation is not supported by your browser'
        }));
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLocation(prev => ({
            ...prev,
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            loading: false,
            error: null,
          }));
          scrollToBottom();
        },
        (error) => {
          let errorMessage = 'Failed to get location';
          switch (error.code) {
            case error.PERMISSION_DENIED:
              errorMessage = 'Location permission denied. Please enable location access in your browser settings.';
              break;
            case error.POSITION_UNAVAILABLE:
              errorMessage = 'Location information is unavailable.';
              break;
            case error.TIMEOUT:
              errorMessage = 'Location request timed out.';
              break;
          }
          setLocation(prev => ({
            ...prev,
            enabled: false,
            loading: false,
            error: errorMessage
          }));
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 60000, // Cache location for 1 minute
        }
      );
    } else {
      // Disable location discovery
      setLocation(prev => ({
        ...prev,
        enabled: false,
        latitude: null,
        longitude: null,
        error: null,
      }));
    }
  };

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
              router.push(chatRoom.url);
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

      // Build request data including location if enabled
      const requestData: Parameters<typeof chatApi.createChat>[0] = { ...formData };
      if (location.enabled && location.latitude !== null && location.longitude !== null) {
        // Round to 6 decimal places (~0.1m accuracy) to fit backend DecimalField(max_digits=9)
        requestData.latitude = Math.round(location.latitude * 1000000) / 1000000;
        requestData.longitude = Math.round(location.longitude * 1000000) / 1000000;
        requestData.discovery_radius_miles = location.discovery_radius_miles;
      }

      console.log('[CreateChatModal] Creating chat room...', requestData);
      const chatRoom = await chatApi.createChat(requestData);
      console.log('[CreateChatModal] Chat room created:', chatRoom);

      // Clear any saved form data on success
      localStorage.removeItem(FORM_STORAGE_KEY);

      // Redirect to the chat room
      router.push(chatRoom.url);
    } catch (err: any) {
      console.error('[CreateChatModal] Error creating chat room:', err);
      setError(err.response?.data?.detail || 'Failed to create chat room');
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      {/* Modal Container */}
      <div className="w-full max-w-lg bg-zinc-800 border border-zinc-700 rounded-2xl shadow-xl relative max-h-[85dvh] overflow-hidden flex flex-col">
        {/* Fixed Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-700">
          <h1 className="text-2xl font-bold text-zinc-50">
            Room Settings
          </h1>
          <button
            onClick={onClose}
            className="p-2 rounded-lg transition-colors text-zinc-300 hover:text-zinc-100 hover:bg-zinc-700 cursor-pointer"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div ref={scrollContainerRef} className="p-6 flex-1 overflow-y-auto">
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
                onClick={() => {
                  setFormData({ ...formData, access_mode: 'private' });
                  scrollToBottom();
                }}
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
                <div className="flex items-center gap-2">
                  <Image className="w-4 h-4 text-cyan-400" />
                  <span className="text-zinc-200">Photo Sharing</span>
                </div>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.voice_enabled}
                  onChange={(e) => setFormData({ ...formData, voice_enabled: e.target.checked })}
                  className="w-5 h-5 text-cyan-400 border-zinc-600 rounded focus:ring-cyan-400"
                />
                <div className="flex items-center gap-2">
                  <Mic className="w-4 h-4 text-cyan-400" />
                  <span className="text-zinc-200">Voice Messages</span>
                </div>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.video_enabled}
                  onChange={(e) => setFormData({ ...formData, video_enabled: e.target.checked })}
                  className="w-5 h-5 text-cyan-400 border-zinc-600 rounded focus:ring-cyan-400"
                />
                <div className="flex items-center gap-2">
                  <Video className="w-4 h-4 text-cyan-400" />
                  <span className="text-zinc-200">Video Messages</span>
                </div>
              </label>
            </div>
          </div>

          {/* Location Discovery */}
          <div>
            <label className="block text-sm font-bold text-zinc-200 mb-3">
              Location Discovery
            </label>
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={location.enabled}
                  onChange={(e) => handleLocationToggle(e.target.checked)}
                  disabled={location.loading}
                  className="w-5 h-5 text-cyan-400 border-zinc-600 rounded focus:ring-cyan-400"
                />
                <div className="flex items-center gap-2">
                  {location.loading ? (
                    <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
                  ) : (
                    <MapPin className="w-4 h-4 text-cyan-400" />
                  )}
                  <span className="text-zinc-200">
                    {location.loading ? 'Getting location...' : 'Discoverable by location'}
                  </span>
                </div>
              </label>

              {/* Location Error */}
              {location.error && (
                <div className="text-sm text-red-400 pl-8">
                  {location.error}
                </div>
              )}

              {/* Radius Selector (shown when location is enabled and acquired) */}
              {location.enabled && location.latitude !== null && (
                <div className="pl-8 pt-2">
                  <label htmlFor="radius" className="block text-sm text-zinc-300 mb-2">
                    Discovery radius
                  </label>
                  <select
                    id="radius"
                    value={location.discovery_radius_miles}
                    onChange={(e) => setLocation(prev => ({
                      ...prev,
                      discovery_radius_miles: parseInt(e.target.value, 10)
                    }))}
                    className="w-full px-4 py-2 border border-zinc-600 rounded-lg bg-zinc-700 text-zinc-50 focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 focus:outline-none"
                  >
                    {radiusOptions.map((miles) => (
                      <option key={miles} value={miles}>
                        {miles} {miles === 1 ? 'mile' : 'miles'}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-zinc-400 mt-2">
                    People within this distance can discover your chat
                  </p>
                </div>
              )}
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
    </div>
  );
}
