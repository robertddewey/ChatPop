'use client';

import React from 'react';
import { Message, ChatRoom } from '@/lib/api';

interface ChatMessageProps {
  message: Message;
  chatRoom: ChatRoom;
  currentUserId?: string;
  onReply: (messageId: string) => void;
  onPin: (messageId: string) => void;
}

// Placeholder ChatMessage component
// TODO: Implement full ChatMessage component
export default function ChatMessage({
  message,
  chatRoom,
  currentUserId,
  onReply,
  onPin,
}: ChatMessageProps) {
  return (
    <div className="p-4 rounded-lg bg-gray-50 dark:bg-gray-800">
      <div className="font-semibold text-sm mb-1">{message.username}</div>
      <div className="text-gray-900 dark:text-white">{message.content}</div>
    </div>
  );
}
