'use client';

import { useEffect } from 'react';
import { useMapEvents, useMap } from 'react-leaflet';

interface MapControllerProps {
  onLocationSelect: (lat: number, lng: number) => void;
  flyToCoords: { lat: number; lng: number } | null;
}

export default function DevLocationPickerMapController({
  onLocationSelect,
  flyToCoords
}: MapControllerProps) {
  const map = useMap();

  // Handle click events
  useMapEvents({
    click(e: { latlng: { lat: number; lng: number } }) {
      onLocationSelect(e.latlng.lat, e.latlng.lng);
    },
  });

  // Fly to coordinates when they change
  useEffect(() => {
    if (flyToCoords && map) {
      map.flyTo([flyToCoords.lat, flyToCoords.lng], 17, {
        duration: 1.5
      });
    }
  }, [flyToCoords, map]);

  return null;
}
