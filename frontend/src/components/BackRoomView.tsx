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
  design?: 'dark-mode';
}

export default function BackRoomView({
  chatRoom,
  backRoom,
  username,
  currentUserId,
  isMember,
  onBack,
  design = 'dark-mode',
}: BackRoomViewProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [showJoinModal, setShowJoinModal] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const isHost = chatRoom.host.id === currentUserId;
  const hasAccess = isMember || isHost;

  // Theme-specific styles
  const getThemeStyles = () => {
    switch (design) {
      case 'pink-dream':
        return {
          header: 'bg-gradient-to-r from-pink-500 via-rose-500 to-red-500 text-white',
          joinButton: 'bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 text-white',
          sendButton: 'bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 text-white',
          inputFocus: 'focus:ring-pink-500',
        };
      case 'ocean-blue':
        return {
          header: 'bg-gradient-to-r from-blue-500 via-sky-500 to-cyan-500 text-white',
          joinButton: 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white',
          sendButton: 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white',
          inputFocus: 'focus:ring-blue-500',
        };
      case 'dark-mode':
        return {
          header: 'bg-cyan-400 text-cyan-950',
          joinButton: 'bg-cyan-400 hover:bg-cyan-500 text-cyan-950',
          sendButton: 'bg-cyan-400 hover:bg-cyan-500 text-cyan-950',
          inputFocus: 'focus:ring-cyan-400',
        };
      default:
        return {
          header: 'bg-gradient-to-r from-pink-500 via-rose-500 to-red-500 text-white',
          joinButton: 'bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 text-white',
          sendButton: 'bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 text-white',
          inputFocus: 'focus:ring-pink-500',
        };
    }
  };

  const styles = getThemeStyles();

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
      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {hasAccess ? (
          <>
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
          </>
        ) : (
          <div className="h-full flex items-center justify-center">
            {/* Empty state for non-members - content TBD */}
          </div>
        )}
      </div>

      {/* Message Input */}
      {hasAccess && (
        <form onSubmit={handleSendMessage} className="p-4 border-t dark:border-gray-700">
          <div className="flex gap-2">
            <input
              type="text"
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              placeholder="Type your message..."
              className={`flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 ${styles.inputFocus} focus:border-transparent`}
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !newMessage.trim()}
              className={`px-6 py-3 disabled:bg-gray-400 rounded-xl font-semibold transition-colors ${styles.sendButton}`}
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
