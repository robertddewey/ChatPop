'use client';

import React, { useState, useEffect, useRef } from 'react';
import { ChatRoom, BackRoom, Message, backRoomApi } from '@/lib/api';
import BackRoomJoinModal from './BackRoomJoinModal';
import ChatMessage from './ChatMessage';

interface BackRoomViewProps {
  chatRoom: ChatRoom;
  backRoom: BackRoom;
  username: string;
  currentUserId?: string;
  isMember: boolean;
  onBack: () => void;
}

export default function BackRoomView({
  chatRoom,
  backRoom,
  username,
  currentUserId,
  isMember,
  onBack,
}: BackRoomViewProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [showJoinModal, setShowJoinModal] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const isHost = chatRoom.host.id === currentUserId;
  const hasAccess = isMember || isHost;

  useEffect(() => {
    if (hasAccess) {
      loadMessages();
      // Poll for new messages every 3 seconds
      const interval = setInterval(loadMessages, 3000);
      return () => clearInterval(interval);
    }
  }, [hasAccess]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadMessages = async () => {
    if (!hasAccess) return;
    try {
      const msgs = await backRoomApi.getMessages(chatRoom.code, username);
      setMessages(msgs);
    } catch (error) {
      console.error('Failed to load back room messages:', error);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMessage.trim() || !hasAccess) return;

    setLoading(true);
    try {
      await backRoomApi.sendMessage(chatRoom.code, username, newMessage.trim());
      setNewMessage('');
      await loadMessages();
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    try {
      await backRoomApi.joinBackRoom(chatRoom.code, username);
      setShowJoinModal(false);
      // Reload to update member status
      window.location.reload();
    } catch (error) {
      console.error('Failed to join back room:', error);
    }
  };

  return (
    <div className="h-full flex flex-col relative">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b dark:border-gray-700 bg-purple-600 text-white">
        <h1 className="text-xl font-bold">Back Room</h1>
        <div className="text-sm opacity-90">
          {backRoom.seats_available} seats left
        </div>
      </div>

      {/* Messages Container */}
      <div className={`flex-1 overflow-y-auto p-4 space-y-4 ${!hasAccess ? 'blur-md pointer-events-none' : ''}`}>
        {messages.map((message) => (
          <ChatMessage
            key={message.id}
            message={message}
            chatRoom={chatRoom}
            currentUserId={currentUserId}
            onReply={() => {}}
            onPin={() => {}}
          />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Join Overlay for non-members */}
      {!hasAccess && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 backdrop-blur-sm">
          <button
            onClick={() => setShowJoinModal(true)}
            className="px-8 py-4 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-bold text-lg shadow-2xl transition-all transform hover:scale-105"
          >
            Join Back Room - ${backRoom.price_per_seat}
          </button>
        </div>
      )}

      {/* Message Input */}
      {hasAccess && (
        <form onSubmit={handleSendMessage} className="p-4 border-t dark:border-gray-700">
          <div className="flex gap-2">
            <input
              type="text"
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              placeholder="Type your message..."
              className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !newMessage.trim()}
              className="px-6 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white rounded-xl font-semibold transition-colors"
            >
              Send
            </button>
          </div>
        </form>
      )}

      {/* Join Modal */}
      {showJoinModal && (
        <BackRoomJoinModal
          backRoom={backRoom}
          onJoin={handleJoin}
          onClose={() => setShowJoinModal(false)}
        />
      )}
    </div>
  );
}
