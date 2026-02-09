'use client';

import { useState, useCallback } from 'react';
import { X } from 'lucide-react';
import dynamic from 'next/dynamic';
import 'leaflet/dist/leaflet.css';

// Dynamically import Leaflet components (they require window/document)
const MapContainer = dynamic(
  () => import('react-leaflet').then((mod) => mod.MapContainer),
  { ssr: false }
);
const TileLayer = dynamic(
  () => import('react-leaflet').then((mod) => mod.TileLayer),
  { ssr: false }
);
const Marker = dynamic(
  () => import('react-leaflet').then((mod) => mod.Marker),
  { ssr: false }
);

interface DevLocationPickerProps {
  onSelect: (coords: { latitude: number; longitude: number }) => void;
  onClose: () => void;
}

// Dynamically import the MapController to avoid SSR issues with react-leaflet hooks
const MapController = dynamic(
  () => import('./DevLocationPickerMapController'),
  { ssr: false }
);

// Popular city presets for quick selection
const CITY_PRESETS = [
  { name: 'New York', lat: 40.7128, lng: -74.0060 },
  { name: 'Los Angeles', lat: 34.0522, lng: -118.2437 },
  { name: 'Chicago', lat: 41.8781, lng: -87.6298 },
  { name: 'San Francisco', lat: 37.7749, lng: -122.4194 },
  { name: 'Miami', lat: 25.7617, lng: -80.1918 },
  { name: 'Seattle', lat: 47.6062, lng: -122.3321 },
  { name: 'Austin', lat: 30.2672, lng: -97.7431 },
  { name: 'Denver', lat: 39.7392, lng: -104.9903 },
  { name: 'Detroit', lat: 42.3314, lng: -83.0458 },
];

export default function DevLocationPicker({ onSelect, onClose }: DevLocationPickerProps) {
  const [selectedCoords, setSelectedCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [flyToCoords, setFlyToCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [customIcon, setCustomIcon] = useState<L.Icon | null>(null);

  // Initialize Leaflet icon on client side
  useEffect(() => {
    if (typeof window !== 'undefined') {
      import('leaflet').then((L) => {
        // Fix default marker icon issue with webpack
        delete (L.Icon.Default.prototype as Record<string, unknown>)._getIconUrl;
        L.Icon.Default.mergeOptions({
          iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
          iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
          shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
        });

        setCustomIcon(new L.Icon.Default());
        setMapReady(true);
      });
    }
  }, []);

  const handleLocationSelect = useCallback((lat: number, lng: number) => {
    setSelectedCoords({ lat, lng });
  }, []);

  const handleConfirm = () => {
    if (selectedCoords) {
      onSelect({ latitude: selectedCoords.lat, longitude: selectedCoords.lng });
    }
  };

  const handlePresetClick = (preset: typeof CITY_PRESETS[0]) => {
    setSelectedCoords({ lat: preset.lat, lng: preset.lng });
    setFlyToCoords({ lat: preset.lat, lng: preset.lng });
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80">
      <div className="w-full max-w-lg bg-zinc-800 border border-zinc-700 rounded-2xl shadow-xl overflow-hidden flex flex-col max-h-[90dvh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-700 bg-amber-900/30">
          <div className="flex items-center gap-2">
            <div className="px-2 py-1 bg-amber-500 text-black text-xs font-bold rounded">DEV</div>
            <h2 className="text-lg font-bold text-zinc-50">Set Debug Location</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-zinc-300 hover:text-zinc-100 hover:bg-zinc-700 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Map */}
        <div className="flex-1 min-h-[300px] relative">
          {mapReady ? (
            <MapContainer
              center={[39.8283, -98.5795]} // Center of USA
              zoom={4}
              className="w-full h-full min-h-[300px]"
              style={{ height: '300px' }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapController onLocationSelect={handleLocationSelect} flyToCoords={flyToCoords} />
              {selectedCoords && customIcon && (
                <Marker position={[selectedCoords.lat, selectedCoords.lng]} icon={customIcon} />
              )}
            </MapContainer>
          ) : (
            <div className="w-full h-[300px] flex items-center justify-center bg-zinc-900">
              <div className="w-8 h-8 border-2 border-zinc-600 border-t-cyan-400 rounded-full animate-spin" />
            </div>
          )}
        </div>

        {/* Quick Presets */}
        <div className="p-4 border-t border-zinc-700">
          <p className="text-xs text-zinc-400 mb-2">Quick select a city:</p>
          <div className="flex flex-wrap gap-2">
            {CITY_PRESETS.map((preset) => (
              <button
                key={preset.name}
                onClick={() => handlePresetClick(preset)}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors cursor-pointer ${
                  selectedCoords?.lat === preset.lat && selectedCoords?.lng === preset.lng
                    ? 'bg-cyan-600 text-white'
                    : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'
                }`}
              >
                {preset.name}
              </button>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-700">
          <button
            onClick={handleConfirm}
            disabled={!selectedCoords}
            className={`w-full px-6 py-3 bg-zinc-700 text-white font-semibold rounded-lg transition-all ${
              selectedCoords
                ? 'hover:bg-zinc-600 cursor-pointer'
                : 'opacity-50 cursor-not-allowed'
            }`}
          >
            Use This Location
          </button>
        </div>
      </div>
    </div>
  );
}
