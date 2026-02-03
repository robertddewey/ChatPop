'use client';

import { X, MapPin, Navigation, Lock, ChevronDown, Users } from 'lucide-react';
import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { locationApi, chatApi, messageApi, LocationSuggestion, LocationAnalysisResponse, NearbyDiscoverableChat } from '@/lib/api';

interface LocationSuggestionsModalProps {
  onClose: () => void;
}

export default function LocationSuggestionsModal({ onClose }: LocationSuggestionsModalProps) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<LocationAnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [locationPermission, setLocationPermission] = useState<'prompt' | 'granted' | 'denied' | 'unknown'>('unknown');

  // User coordinates for reuse
  const [userCoords, setUserCoords] = useState<{ latitude: number; longitude: number } | null>(null);

  // Selection state for Area Chat Rooms and Nearby Chats
  const [selectingAreaIndex, setSelectingAreaIndex] = useState<number | null>(null);
  const [selectingVenueIndex, setSelectingVenueIndex] = useState<number | null>(null);
  const [selectingNearbyIndex, setSelectingNearbyIndex] = useState<number | null>(null);
  const [selectionError, setSelectionError] = useState<string | null>(null);

  // Nearby discoverable chats state
  const [nearbyChats, setNearbyChats] = useState<NearbyDiscoverableChat[]>([]);
  const [nearbyChatsLoading, setNearbyChatsLoading] = useState(false);
  const [nearbyChatsError, setNearbyChatsError] = useState<string | null>(null);
  const [selectedRadius, setSelectedRadius] = useState(1);
  const [radiusOptions, setRadiusOptions] = useState<number[]>([1, 5, 10, 25, 50]);
  const [nearbyChatsOffset, setNearbyChatsOffset] = useState(0);
  const [nearbyChatsHasMore, setNearbyChatsHasMore] = useState(false);
  const [nearbyChatsTotal, setNearbyChatsTotal] = useState(0);

  // Ref for infinite scroll
  const nearbyChatsEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Check if any selection is in progress
  const isSelecting = selectingAreaIndex !== null || selectingVenueIndex !== null || selectingNearbyIndex !== null;

  // Check location permission status on mount
  useEffect(() => {
    document.body.style.overflow = 'hidden';

    // Check if geolocation is available
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser');
      setLocationPermission('denied');
    } else if (navigator.permissions) {
      // Check permission status
      navigator.permissions.query({ name: 'geolocation' }).then((permissionStatus) => {
        setLocationPermission(permissionStatus.state as 'prompt' | 'granted' | 'denied');

        // Listen for permission changes
        permissionStatus.onchange = () => {
          setLocationPermission(permissionStatus.state as 'prompt' | 'granted' | 'denied');
        };
      }).catch(() => {
        setLocationPermission('prompt');
      });
    } else {
      setLocationPermission('prompt');
    }

    // Fetch radius options from config
    chatApi.getConfig().then((config) => {
      if (config.discovery_radius_options?.length > 0) {
        setRadiusOptions(config.discovery_radius_options);
        setSelectedRadius(config.discovery_radius_options[0]); // Default to first (smallest)
      }
    }).catch(() => {
      // Keep defaults if config fails
    });

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  // Fetch nearby discoverable chats
  const fetchNearbyChats = useCallback(async (coords: { latitude: number; longitude: number }, radius: number, offset: number = 0, append: boolean = false) => {
    setNearbyChatsLoading(true);
    setNearbyChatsError(null);

    try {
      const response = await locationApi.getNearbyDiscoverableChats({
        latitude: coords.latitude,
        longitude: coords.longitude,
        radius,
        offset,
        limit: 20,
      });

      if (append) {
        setNearbyChats(prev => [...prev, ...response.chats]);
      } else {
        setNearbyChats(response.chats);
      }
      setNearbyChatsOffset(offset + response.chats.length);
      setNearbyChatsHasMore(response.has_more);
      setNearbyChatsTotal(response.total_count);
    } catch (err: any) {
      console.error('❌ Error fetching nearby chats:', err);
      setNearbyChatsError(err.response?.data?.error || 'Failed to load nearby chats');
    } finally {
      setNearbyChatsLoading(false);
    }
  }, []);

  // Handle radius change
  const handleRadiusChange = (newRadius: number) => {
    setSelectedRadius(newRadius);
    if (userCoords) {
      // Reset and fetch with new radius
      setNearbyChatsOffset(0);
      fetchNearbyChats(userCoords, newRadius, 0, false);
    }
  };

  // Load more chats (infinite scroll)
  const loadMoreChats = useCallback(() => {
    if (nearbyChatsLoading || !nearbyChatsHasMore || !userCoords) return;
    fetchNearbyChats(userCoords, selectedRadius, nearbyChatsOffset, true);
  }, [nearbyChatsLoading, nearbyChatsHasMore, userCoords, selectedRadius, nearbyChatsOffset, fetchNearbyChats]);

  // Infinite scroll observer
  useEffect(() => {
    if (!nearbyChatsEndRef.current || !result) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && nearbyChatsHasMore && !nearbyChatsLoading) {
          loadMoreChats();
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(nearbyChatsEndRef.current);

    return () => observer.disconnect();
  }, [nearbyChatsHasMore, nearbyChatsLoading, loadMoreChats, result]);

  const requestLocation = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Request geolocation
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 60000, // Cache for 1 minute
        });
      });

      const { latitude, longitude } = position.coords;
      console.log('📍 Location obtained:', latitude, longitude);

      // Store coordinates for reuse
      setUserCoords({ latitude, longitude });

      // Fetch suggestions from API
      const response = await locationApi.getSuggestions(latitude, longitude);
      console.log('✅ Location suggestions received:', response);
      setResult(response);

      // Also fetch nearby discoverable chats
      fetchNearbyChats({ latitude, longitude }, selectedRadius, 0, false);

    } catch (err: any) {
      console.error('❌ Location error:', err);

      // Handle geolocation errors
      if (err.code === 1) {
        setError('Location access denied. Please allow location access in your browser settings and try again.');
        setLocationPermission('denied');
      } else if (err.code === 2) {
        setError('Unable to determine your location. Please try again.');
      } else if (err.code === 3) {
        setError('Location request timed out. Please try again.');
      } else {
        // Handle API errors
        const errorMessage = err.response?.data?.error || err.response?.data?.detail || 'Failed to get nearby chats. Please try again.';
        setError(errorMessage);
      }
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Area Chat Room click (AI-generated, needs API call)
  const handleAreaClick = async (suggestion: LocationSuggestion, index: number) => {
    if (!result || isSelecting) return;

    setSelectingAreaIndex(index);
    setSelectionError(null);

    try {
      const response = await messageApi.createChatFromLocation({
        location_analysis_id: result.id,
        room_code: suggestion.key,
      });

      console.log('Location room created/joined:', response);
      router.push(response.chat_room.url);
    } catch (err: any) {
      console.error('Failed to create/join location room:', err);
      setSelectionError(err.response?.data?.detail || err.message || 'Failed to join room');
      setSelectingAreaIndex(null);
    }
  };

  // Handle Venue click (AI-generated, needs API call)
  const handleVenueClick = async (suggestion: LocationSuggestion, index: number) => {
    if (!result || isSelecting) return;

    setSelectingVenueIndex(index);
    setSelectionError(null);

    try {
      const response = await messageApi.createChatFromLocation({
        location_analysis_id: result.id,
        room_code: suggestion.key,
      });

      console.log('Location room created/joined:', response);
      router.push(response.chat_room.url);
    } catch (err: any) {
      console.error('Failed to create/join location room:', err);
      setSelectionError(err.response?.data?.detail || err.message || 'Failed to join room');
      setSelectingVenueIndex(null);
    }
  };

  // Handle Nearby Chat click (user-generated, just navigate)
  const handleNearbyChatClick = (chat: NearbyDiscoverableChat, index: number) => {
    if (isSelecting) return;

    setSelectingNearbyIndex(index);
    // Navigate directly to the existing room
    router.push(chat.url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      {/* Modal Container */}
      <div className="w-full max-w-md bg-zinc-800 border border-zinc-700 rounded-2xl shadow-xl relative max-h-[85dvh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-700">
          <div>
            <h1 className="text-2xl font-bold text-zinc-50 flex items-center gap-2">
              <MapPin className="w-6 h-6" />
              {isLoading ? 'Finding chats...' : result?.success ? 'Nearby Places' : 'Start a local chat'}
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              {isLoading ? 'Getting nearby chats' : result?.success ? `📍 ${result.location.city || 'Your area'}` : 'Tap to find chats near you'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg transition-colors text-zinc-300 hover:text-zinc-100 hover:bg-zinc-700 cursor-pointer"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div ref={scrollContainerRef} className="p-6 flex-1 overflow-y-auto">
          {/* Initial State - Request Location */}
          {!isLoading && !result && (
            <div className="flex flex-col items-center justify-center space-y-6">
              {/* Location Button */}
              <button
                onClick={requestLocation}
                disabled={locationPermission === 'denied'}
                className={`w-24 h-24 rounded-full flex items-center justify-center transition-all transform shadow-xl ${
                  locationPermission === 'denied'
                    ? 'bg-zinc-600 text-zinc-400 cursor-not-allowed'
                    : 'bg-cyan-500 hover:bg-cyan-600 hover:scale-105 text-white cursor-pointer'
                }`}
              >
                <Navigation className="w-10 h-10" />
              </button>

              <p className="text-zinc-300 text-center max-w-sm">
                {locationPermission === 'denied'
                  ? 'Location access is blocked. Please enable location in your browser settings.'
                  : 'Tap to share your location and discover nearby chat rooms'}
              </p>

              {error && (
                <div className="w-full p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              )}
            </div>
          )}

          {/* Loading State */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              <div className="w-16 h-16 border-4 border-zinc-600 border-t-cyan-400 rounded-full animate-spin"></div>
              <p className="text-zinc-300 text-lg font-medium">Getting nearby chats...</p>
            </div>
          )}

          {/* Results State */}
          {result && result.success && (() => {
            // Filter suggestions into areas and venues
            const areaTypes = ['neighborhood', 'city', 'metro'];
            const areas = result.suggestions?.filter(s => areaTypes.includes(s.type)) || [];
            const venues = result.suggestions?.filter(s => !areaTypes.includes(s.type)) || [];

            return (
              <div className="space-y-6">
                {/* Area Chat Rooms */}
                {areas.length > 0 && (
                  <div>
                    <h2 className="text-lg font-bold text-zinc-200 mb-3">
                      Area Chat Rooms
                    </h2>
                    <div className="space-y-3">
                      {areas.map((area, idx) => {
                        const isSelectingThis = selectingAreaIndex === idx;
                        const isDisabled = isSelecting && !isSelectingThis;

                        return (
                          <button
                            key={area.key}
                            onClick={() => handleAreaClick(area, idx)}
                            disabled={isSelecting}
                            className={`w-full text-left p-4 bg-zinc-900/50 border rounded-lg transition-all ${
                              isSelectingThis
                                ? 'border-cyan-400 bg-cyan-900/20'
                                : isDisabled
                                ? 'border-zinc-700 opacity-50 cursor-not-allowed'
                                : 'border-zinc-600 hover:border-cyan-400 hover:bg-zinc-800/50 cursor-pointer'
                            }`}
                          >
                            {/* Name and Badge */}
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-zinc-400">#{idx + 1}</span>
                                <h3 className="text-base font-bold text-zinc-50">{area.name}</h3>
                                <span className="px-2 py-0.5 bg-cyan-900/40 border border-cyan-700 text-cyan-300 text-xs font-semibold rounded uppercase">
                                  {area.type}
                                </span>
                              </div>
                              {isSelectingThis && (
                                <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                              )}
                            </div>
                            {/* Description */}
                            <p className="text-sm text-zinc-300">Chat with others in {area.name}</p>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Nearby Places */}
                {venues.length > 0 && (
                  <div>
                    <h2 className="text-lg font-bold text-zinc-200 mb-3">
                      Nearby Places
                    </h2>
                    <div className="space-y-3">
                      {venues.map((venue, idx) => {
                        const isSelectingThis = selectingVenueIndex === idx;
                        const isDisabled = isSelecting && !isSelectingThis;

                        return (
                          <button
                            key={venue.key}
                            onClick={() => handleVenueClick(venue, idx)}
                            disabled={isSelecting}
                            className={`w-full text-left p-4 bg-zinc-900/50 border rounded-lg transition-all ${
                              isSelectingThis
                                ? 'border-purple-400 bg-purple-900/20'
                                : isDisabled
                                ? 'border-zinc-700 opacity-50 cursor-not-allowed'
                                : 'border-zinc-600 hover:border-purple-400 hover:bg-zinc-800/50 cursor-pointer'
                            }`}
                          >
                            {/* Name and Badge */}
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-zinc-400">#{idx + 1}</span>
                                <h3 className="text-base font-bold text-zinc-50">{venue.name}</h3>
                                <span className="px-2 py-0.5 bg-purple-900/40 border border-purple-700 text-purple-300 text-xs font-semibold rounded uppercase">
                                  {venue.type}
                                </span>
                              </div>
                              {isSelectingThis && (
                                <div className="w-5 h-5 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
                              )}
                            </div>
                            {/* Description */}
                            <p className="text-sm text-zinc-300">Chat with others at {venue.name}</p>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Nearby Discoverable Chats */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-lg font-bold text-zinc-200">
                      Nearby Chats
                    </h2>
                    {/* Radius Dropdown */}
                    <div className="relative">
                      <select
                        value={selectedRadius}
                        onChange={(e) => handleRadiusChange(Number(e.target.value))}
                        className="appearance-none bg-zinc-700 border border-zinc-600 text-zinc-200 text-sm rounded-lg px-3 py-1.5 pr-8 cursor-pointer hover:bg-zinc-600 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                      >
                        {radiusOptions.map((r) => (
                          <option key={r} value={r}>
                            {r} mi
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 pointer-events-none" />
                    </div>
                  </div>

                  {/* Nearby chats list */}
                  <div className="space-y-3">
                    {nearbyChats.map((chat, idx) => {
                      const isSelectingThis = selectingNearbyIndex === idx;
                      const isDisabled = isSelecting && !isSelectingThis;

                      return (
                        <button
                          key={chat.id}
                          onClick={() => handleNearbyChatClick(chat, idx)}
                          disabled={isSelecting}
                          className={`w-full text-left p-4 bg-zinc-900/50 border rounded-lg transition-all ${
                            isSelectingThis
                              ? 'border-green-400 bg-green-900/20'
                              : isDisabled
                              ? 'border-zinc-700 opacity-50 cursor-not-allowed'
                              : 'border-zinc-600 hover:border-green-400 hover:bg-zinc-800/50 cursor-pointer'
                          }`}
                        >
                          {/* Top row: Rank, Name, Distance */}
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                              <span className="text-xs font-bold text-zinc-400 flex-shrink-0">#{idx + 1}</span>
                              <h3 className="text-base font-bold text-zinc-50 truncate">{chat.name}</h3>
                              {chat.access_mode === 'private' && (
                                <Lock className="w-4 h-4 text-yellow-500 flex-shrink-0" />
                              )}
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                              <span className="text-sm text-zinc-400">
                                {chat.distance_miles} mi
                              </span>
                              {isSelectingThis && (
                                <div className="w-5 h-5 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
                              )}
                            </div>
                          </div>
                          {/* Bottom row: Host and participants */}
                          <div className="flex items-center gap-3 text-sm text-zinc-400">
                            <span>@{chat.host_username}</span>
                            <span className="flex items-center gap-1">
                              <Users className="w-3.5 h-3.5" />
                              {chat.participant_count}
                            </span>
                          </div>
                        </button>
                      );
                    })}

                    {/* Loading indicator for infinite scroll */}
                    {nearbyChatsLoading && nearbyChats.length > 0 && (
                      <div className="flex justify-center py-4">
                        <div className="w-6 h-6 border-2 border-zinc-600 border-t-cyan-400 rounded-full animate-spin"></div>
                      </div>
                    )}

                    {/* Initial loading for nearby chats */}
                    {nearbyChatsLoading && nearbyChats.length === 0 && (
                      <div className="flex flex-col items-center py-6 space-y-2">
                        <div className="w-6 h-6 border-2 border-zinc-600 border-t-cyan-400 rounded-full animate-spin"></div>
                        <p className="text-sm text-zinc-400">Loading nearby chats...</p>
                      </div>
                    )}

                    {/* Empty state */}
                    {!nearbyChatsLoading && nearbyChats.length === 0 && !nearbyChatsError && (
                      <div className="text-center py-6">
                        <p className="text-zinc-400 text-sm">
                          No discoverable chats within {selectedRadius} mile{selectedRadius !== 1 ? 's' : ''}
                        </p>
                        <p className="text-zinc-500 text-xs mt-1">
                          Try increasing the search radius
                        </p>
                      </div>
                    )}

                    {/* Error state */}
                    {nearbyChatsError && (
                      <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                        <p className="text-red-400 text-sm">{nearbyChatsError}</p>
                      </div>
                    )}

                    {/* Infinite scroll trigger */}
                    <div ref={nearbyChatsEndRef} className="h-1" />
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Error State after trying */}
          {!isLoading && error && !result && (
            <div className="space-y-4">
              <button
                onClick={() => {
                  setError(null);
                }}
                className="w-full px-4 py-3 bg-zinc-700 hover:bg-zinc-600 text-zinc-100 rounded-lg font-medium transition-colors"
              >
                Try Again
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-700">
          {selectionError && (
            <div className="mb-3 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300 text-sm">
              {selectionError}
            </div>
          )}
          {!isLoading && result && (
            <p className="text-center text-zinc-400 text-sm mb-3">
              Tap a chat room to join
            </p>
          )}
          <button
            onClick={onClose}
            disabled={isLoading || isSelecting}
            className={`w-full px-6 py-3 bg-zinc-700 text-white font-semibold rounded-lg transition-all ${
              isLoading || isSelecting ? 'opacity-50 cursor-not-allowed' : 'hover:bg-zinc-600 cursor-pointer'
            }`}
          >
            {isSelecting ? 'Joining room...' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  );
}
