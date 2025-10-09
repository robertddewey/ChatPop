'use client';

import React from 'react';
import { Gamepad2, MessageSquare } from 'lucide-react';
import FloatingActionButton from './FloatingActionButton';

interface GameRoomTabProps {
  isInBackRoom: boolean;
  hasBackRoom: boolean;
  onClick: () => void;
  hasNewMessages?: boolean;
  design?: 'dark-mode' | 'pink-dream' | 'ocean-blue' | 'light-mode';
}

export default function GameRoomTab({
  isInBackRoom,
  hasBackRoom,
  onClick,
  hasNewMessages = false,
  design = 'dark-mode',
}: GameRoomTabProps) {
  if (!hasBackRoom) return null;

  return (
    <FloatingActionButton
      icon={Gamepad2}
      toggledIcon={MessageSquare}
      onClick={onClick}
      isToggled={isInBackRoom}
      hasNotification={hasNewMessages}
      position="right"
      verticalPosition="center"
      ariaLabel="Open Game Room"
      toggledAriaLabel="Return to Main Chat"
      design={design}
      initialBounce={hasBackRoom}
    />
  );
}
