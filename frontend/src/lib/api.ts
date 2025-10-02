import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000';

// Create axios instance
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

// Types
export interface User {
  id: string;
  email: string;
  display_name: string;
  first_name: string;
  last_name: string;
  email_notifications: boolean;
  push_notifications: boolean;
  subscriber_count: number;
  subscription_count: number;
  created_at: string;
  last_active: string;
}

export interface ChatRoom {
  id: string;
  code: string;
  name: string;
  description: string;
  host: User;
  url: string;
  access_mode: 'public' | 'private';
  voice_enabled: boolean;
  video_enabled: boolean;
  photo_enabled: boolean;
  message_count: number;
  has_back_room: boolean;
  is_active: boolean;
  created_at: string;
}

export interface ReplyToMessage {
  id: string;
  username: string;
  content: string;
  is_from_host: boolean;
}

export interface Message {
  id: string;
  chat_room: string;
  username: string;
  user: User | null;
  message_type: 'normal' | 'host' | 'system';
  content: string;
  reply_to: string | null;
  reply_to_message: ReplyToMessage | null;
  is_pinned: boolean;
  pinned_at: string | null;
  pinned_until: string | null;
  pin_amount_paid: string;
  is_from_host: boolean;
  time_until_unpin: number | null;
  created_at: string;
  is_deleted: boolean;
}

export interface BackRoom {
  id: string;
  chat_room: string;
  price_per_seat: string;
  max_seats: number;
  seats_occupied: number;
  seats_available: number;
  is_full: boolean;
  is_active: boolean;
  created_at: string;
}

// API Functions
export const authApi = {
  register: async (data: { email: string; password: string; password_confirm: string; display_name?: string }) => {
    const response = await api.post('/api/auth/register/', data);
    return response.data;
  },

  login: async (email: string, password: string) => {
    const response = await api.post('/api/auth/login/', { email, password });
    if (response.data.token) {
      localStorage.setItem('auth_token', response.data.token);
    }
    return response.data;
  },

  logout: async () => {
    await api.post('/api/auth/logout/');
    localStorage.removeItem('auth_token');
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get('/api/auth/me/');
    return response.data;
  },
};

export const chatApi = {
  createChat: async (data: {
    name: string;
    description?: string;
    access_mode: 'public' | 'private';
    access_code?: string;
    voice_enabled?: boolean;
    video_enabled?: boolean;
    photo_enabled?: boolean;
  }): Promise<ChatRoom> => {
    const response = await api.post('/api/chats/create/', data);
    return response.data;
  },

  getChatByCode: async (code: string): Promise<ChatRoom> => {
    const response = await api.get(`/api/chats/${code}/`);
    return response.data;
  },

  joinChat: async (code: string, username: string, accessCode?: string) => {
    const response = await api.post(`/api/chats/${code}/join/`, {
      username,
      access_code: accessCode,
    });
    return response.data;
  },

  getMyChats: async (): Promise<ChatRoom[]> => {
    const response = await api.get('/api/chats/my-chats/');
    return response.data.results || response.data;
  },

  updateChat: async (code: string, data: {
    name?: string;
    description?: string;
    access_mode?: 'public' | 'private';
    access_code?: string;
    voice_enabled?: boolean;
    video_enabled?: boolean;
    photo_enabled?: boolean;
    is_active?: boolean;
  }): Promise<ChatRoom> => {
    const response = await api.put(`/api/chats/${code}/update/`, data);
    return response.data;
  },
};

export const messageApi = {
  getMessages: async (code: string): Promise<Message[]> => {
    const response = await api.get(`/api/chats/${code}/messages/`);
    return response.data.results || response.data;
  },

  sendMessage: async (code: string, username: string, content: string): Promise<Message> => {
    const response = await api.post(`/api/chats/${code}/messages/send/`, {
      username,
      content,
    });
    return response.data;
  },

  pinMessage: async (code: string, messageId: string, amount: number, duration_minutes: number = 60) => {
    const response = await api.post(`/api/chats/${code}/messages/${messageId}/pin/`, {
      amount,
      duration_minutes,
    });
    return response.data;
  },
};

export const backRoomApi = {
  getBackRoom: async (code: string): Promise<BackRoom> => {
    const response = await api.get(`/api/chats/${code}/backroom/`);
    return response.data;
  },

  joinBackRoom: async (code: string, username: string) => {
    const response = await api.post(`/api/chats/${code}/backroom/join/`, { username });
    return response.data;
  },

  getMessages: async (code: string, username: string): Promise<Message[]> => {
    const response = await api.get(`/api/chats/${code}/backroom/messages/`, {
      data: { username }
    });
    return response.data.results || response.data;
  },

  sendMessage: async (code: string, username: string, content: string, replyTo?: string): Promise<Message> => {
    const response = await api.post(`/api/chats/${code}/backroom/messages/send/`, {
      username,
      content,
      reply_to: replyTo
    });
    return response.data;
  },

  getMembers: async (code: string) => {
    const response = await api.get(`/api/chats/${code}/backroom/members/`);
    return response.data;
  },
};
