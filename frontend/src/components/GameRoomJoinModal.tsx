'use client';

import React, { useState, useEffect } from 'react';
import { X, Users, DollarSign } from 'lucide-react';
import { BackRoom } from '@/lib/api';
import { getModalTheme } from '@/lib/modal-theme';

interface GameRoomJoinModalProps {
  backRoom: BackRoom;
  onJoin: () => void;
  onClose: () => void;
}

export default function GameRoomJoinModal({
  backRoom,
  onJoin,
  onClose,
}: GameRoomJoinModalProps) {
  const [loading, setLoading] = useState(false);

  // Prevent body scrolling when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, []);

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

  // Always use dark mode for consistency with other modals
  const mt = getModalTheme(true);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className={`absolute inset-0 ${mt.backdrop}`}
        onClick={onClose}
      />

      {/* Modal */}
      <div className={`relative ${mt.container} ${mt.border} ${mt.rounded} shadow-2xl max-w-md w-full p-6`}>
        {/* Close button */}
        <button
          onClick={onClose}
          className={`absolute top-4 right-4 p-2 rounded-lg transition-colors ${mt.closeButton}`}
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="mb-6">
          <div className="w-16 h-16 bg-purple-900/30 rounded-full flex items-center justify-center mb-4">
            <Users className="w-8 h-8 text-purple-400" />
          </div>
          <h2 className={`text-2xl font-bold ${mt.title} mb-2`}>
            Join Back Room
          </h2>
          <p className={mt.body}>
            Get exclusive access to chat directly with the host
          </p>
        </div>

        {/* Info Cards */}
        <div className="space-y-3 mb-6">
          <div className="flex items-center justify-between p-4 bg-purple-900/20 rounded-xl">
            <div className="flex items-center gap-3">
              <DollarSign className="w-5 h-5 text-purple-400" />
              <span className="text-sm font-medium text-zinc-300">
                Price per seat
              </span>
            </div>
            <span className="text-lg font-bold text-purple-400">
              ${backRoom.price_per_seat}
            </span>
          </div>

          <div className="flex items-center justify-between p-4 bg-zinc-800 rounded-xl">
            <div className="flex items-center gap-3">
              <Users className={`w-5 h-5 ${mt.body}`} />
              <span className="text-sm font-medium text-zinc-300">
                Seats available
              </span>
            </div>
            <span className={`text-lg font-bold ${mt.title}`}>
              {backRoom.seats_available} / {backRoom.max_seats}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className={`flex-1 px-4 py-3 rounded-xl font-semibold transition-colors ${mt.secondaryButton}`}
          >
            Cancel
          </button>
          <button
            onClick={handleJoin}
            disabled={loading || backRoom.is_full}
            className={`flex-1 px-4 py-3 rounded-xl font-semibold transition-colors disabled:bg-gray-400 disabled:text-white ${mt.primaryButton}`}
          >
            {loading ? 'Joining...' : backRoom.is_full ? 'Full' : `Join - $${backRoom.price_per_seat}`}
          </button>
        </div>
      </div>
    </div>
  );
}
