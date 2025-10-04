'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Message, ChatRoom } from '@/lib/api';
import { Play, Pause } from 'lucide-react';

interface ChatMessageProps {
  message: Message;
  chatRoom: ChatRoom;
  currentUserId?: string;
  onReply: (messageId: string) => void;
  onPin: (messageId: string) => void;
}

// Voice Player Component
function VoicePlayer({ voiceUrl }: { voiceUrl: string }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const audio = new Audio(voiceUrl);
    audioRef.current = audio;

    audio.addEventListener('loadedmetadata', () => {
      setDuration(audio.duration);
    });

    audio.addEventListener('timeupdate', () => {
      setCurrentTime(audio.currentTime);
    });

    audio.addEventListener('ended', () => {
      setIsPlaying(false);
      setCurrentTime(0);
    });

    return () => {
      audio.pause();
      audio.src = '';
    };
  }, [voiceUrl]);

  const togglePlay = () => {
    if (!audioRef.current) return;

    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="flex items-center gap-2 bg-gradient-to-r from-purple-100 to-blue-100 dark:from-purple-900/30 dark:to-blue-900/30 p-3 rounded-lg">
      <button
        onClick={togglePlay}
        className="p-2 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700 transition-all flex-shrink-0"
      >
        {isPlaying ? <Pause size={16} /> : <Play size={16} />}
      </button>
      <div className="flex-1">
        <div className="h-1 bg-gray-300 dark:bg-gray-600 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-purple-600 to-blue-600 transition-all duration-100"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1 font-mono">
          {formatTime(currentTime)} / {formatTime(duration)}
        </div>
      </div>
    </div>
  );
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

      {message.voice_url ? (
        <VoicePlayer voiceUrl={message.voice_url} />
      ) : (
        <div className="text-gray-900 dark:text-white">{message.content}</div>
      )}
    </div>
  );
}
