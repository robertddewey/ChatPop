'use client';

import React from 'react';
import { ChatRoom } from '@/lib/api';

interface GameRoomViewProps {
  chatRoom: ChatRoom;
  username: string;
  currentUserId?: string;
  onBack: () => void;
  design?: 'dark-mode';
}

export default function GameRoomView({
  chatRoom,
  username,
  currentUserId,
  onBack,
  design = 'dark-mode',
}: GameRoomViewProps) {
  return (
    <div className="h-full flex flex-col relative overflow-hidden">
      {/* Gaming Background - Fixed behind everything */}
      <div className="absolute inset-0 pointer-events-none bg-[url('/game-room-bg.svg')] bg-center bg-no-repeat bg-cover opacity-30" />

      {/* Static Content Area */}
      <div className="flex-1 overflow-y-auto p-4 relative z-10">
        <div className="h-full flex items-center justify-center">
          {/* Static fixture - just the gaming background */}
        </div>
      </div>
    </div>
  );
}
