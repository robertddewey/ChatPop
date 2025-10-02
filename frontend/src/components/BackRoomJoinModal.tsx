'use client';

import React, { useState } from 'react';
import { X, Users, DollarSign } from 'lucide-react';
import { BackRoom } from '@/lib/api';

interface BackRoomJoinModalProps {
  backRoom: BackRoom;
  onJoin: () => void;
  onClose: () => void;
}

export default function BackRoomJoinModal({
  backRoom,
  onJoin,
  onClose,
}: BackRoomJoinModalProps) {
  const [loading, setLoading] = useState(false);

  const handleJoin = async () => {
    setLoading(true);
    try {
      await onJoin();
    } catch (error) {
      console.error('Failed to join back room:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white dark:bg-gray-900 rounded-2xl shadow-2xl max-w-md w-full p-6">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="mb-6">
          <div className="w-16 h-16 bg-purple-100 dark:bg-purple-900/30 rounded-full flex items-center justify-center mb-4">
            <Users className="w-8 h-8 text-purple-600 dark:text-purple-400" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            Join Back Room
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Get exclusive access to chat directly with the host
          </p>
        </div>

        {/* Info Cards */}
        <div className="space-y-3 mb-6">
          <div className="flex items-center justify-between p-4 bg-purple-50 dark:bg-purple-900/20 rounded-xl">
            <div className="flex items-center gap-3">
              <DollarSign className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Price per seat
              </span>
            </div>
            <span className="text-lg font-bold text-purple-600 dark:text-purple-400">
              ${backRoom.price_per_seat}
            </span>
          </div>

          <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 rounded-xl">
            <div className="flex items-center gap-3">
              <Users className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Seats available
              </span>
            </div>
            <span className="text-lg font-bold text-gray-900 dark:text-white">
              {backRoom.seats_available} / {backRoom.max_seats}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleJoin}
            disabled={loading || backRoom.is_full}
            className="flex-1 px-4 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white rounded-xl font-semibold transition-colors"
          >
            {loading ? 'Joining...' : backRoom.is_full ? 'Full' : `Join - $${backRoom.price_per_seat}`}
          </button>
        </div>
      </div>
    </div>
  );
}
