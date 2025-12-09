'use client';

import { X, MapPin, Navigation } from 'lucide-react';
import { useState, useEffect } from 'react';
import { locationApi, LocationSuggestion, LocationAnalysisResponse } from '@/lib/api';

interface LocationSuggestionsModalProps {
  onClose: () => void;
}

export default function LocationSuggestionsModal({ onClose }: LocationSuggestionsModalProps) {
  const [isRequestingLocation, setIsRequestingLocation] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<LocationAnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [locationPermission, setLocationPermission] = useState<'prompt' | 'granted' | 'denied' | 'unknown'>('unknown');

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

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  const requestLocation = async () => {
    setIsRequestingLocation(true);
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

      // Now fetch suggestions
      await fetchSuggestions(latitude, longitude);

    } catch (err: any) {
      console.error('❌ Location access denied:', err);

      if (err.code === 1) {
        setError('Location access denied. Please allow location access in your browser settings and try again.');
        setLocationPermission('denied');
      } else if (err.code === 2) {
        setError('Unable to determine your location. Please try again.');
      } else if (err.code === 3) {
        setError('Location request timed out. Please try again.');
      } else {
        setError('Failed to get your location. Please try again.');
      }
    } finally {
      setIsRequestingLocation(false);
    }
  };

  const fetchSuggestions = async (latitude: number, longitude: number) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await locationApi.getSuggestions(latitude, longitude);
      console.log('✅ Location suggestions received:', response);
      setResult(response);
    } catch (err: any) {
      console.error('❌ Location suggestions failed:', err.response?.data || err.message);
      const errorMessage = err.response?.data?.error || err.response?.data?.detail || 'Failed to get suggestions';
      setError(errorMessage);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
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
              {isRequestingLocation ? 'Getting Location...' : isLoading ? 'Finding Places...' : result?.success ? 'Nearby Places' : 'Start a local chat'}
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              {isRequestingLocation ? '📍 Requesting your location' : isLoading ? '🔍 Searching nearby venues' : result?.success ? `📍 ${result.location.city || 'Your area'}` : 'Tap to find chats near you'}
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
        <div className="p-6 flex-1 overflow-y-auto">
          {/* Initial State - Request Location */}
          {!isRequestingLocation && !isLoading && !result && (
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

          {/* Requesting Location State */}
          {isRequestingLocation && (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              <div className="w-16 h-16 border-4 border-zinc-600 border-t-cyan-400 rounded-full animate-spin"></div>
              <p className="text-zinc-300 text-lg font-medium">Getting your location...</p>
              <p className="text-zinc-500 text-sm">Please allow location access if prompted</p>
            </div>
          )}

          {/* Loading Suggestions State */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              <div className="w-16 h-16 border-4 border-zinc-600 border-t-cyan-400 rounded-full animate-spin"></div>
              <p className="text-zinc-300 text-lg font-medium">Finding nearby places...</p>
              <p className="text-zinc-500 text-sm">Searching for chat suggestions</p>
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
                    <div className="space-y-2">
                      {areas.map((area) => (
                        <div
                          key={area.key}
                          className="p-3 bg-zinc-900/50 border border-zinc-600 rounded-lg hover:border-cyan-400 transition-colors cursor-pointer"
                        >
                          <h3 className="text-base font-bold text-zinc-50">{area.name}</h3>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Nearby Places */}
                {venues.length > 0 && (
                  <div>
                    <h2 className="text-lg font-bold text-zinc-200 mb-3">
                      Nearby Places
                    </h2>
                    <div className="space-y-2">
                      {venues.map((venue) => (
                        <div
                          key={venue.key}
                          className="p-3 bg-zinc-900/50 border border-zinc-600 rounded-lg hover:border-cyan-400 transition-colors cursor-pointer"
                        >
                          <h3 className="text-base font-bold text-zinc-50">{venue.name}</h3>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}

          {/* Error State after trying */}
          {!isRequestingLocation && !isLoading && error && !result && (
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
          <button
            onClick={onClose}
            className="w-full px-6 py-3 bg-[#404eed] text-white font-semibold rounded-lg transition-all hover:bg-[#3640d9] cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
