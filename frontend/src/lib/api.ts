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
  reserved_username: string;
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
  default_theme: string;
  theme_locked: boolean;
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
  username_is_reserved: boolean;
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
  register: async (data: { email: string; password: string; reserved_username?: string }) => {
    const response = await api.post('/api/auth/register/', data);
    return response.data;
  },

  login: async (email: string, password: string) => {
    const response = await api.post('/api/auth/login/', { email, password });
    if (response.data.token) {
      localStorage.setItem('auth_token', response.data.token);
      // Dispatch auth-change event to notify other components
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event('auth-change'));
      }
    }
    return response.data;
  },

  logout: async () => {
    try {
      // Only call API if we have a token (real user)
      const token = localStorage.getItem('auth_token');
      if (token) {
        await api.post('/api/auth/logout/');
      }
    } catch (error) {
      // Ignore logout API errors - we'll clear local storage anyway
      console.warn('Logout API call failed, clearing local storage anyway:', error);
    } finally {
      // Always clear local storage
      localStorage.removeItem('auth_token');
    }
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get('/api/auth/me/');
    return response.data;
  },

  checkUsername: async (username: string): Promise<{ available: boolean; message: string }> => {
    const response = await api.get('/api/auth/check-username/', {
      params: { username },
    });
    return response.data;
  },

  suggestUsername: async (): Promise<{ username: string }> => {
    const response = await api.post('/api/auth/suggest-username/');
    return response.data;
  },
};

export interface ChatParticipation {
  has_joined: boolean;
  username?: string;
  username_is_reserved?: boolean;
  first_joined_at?: string;
  last_seen_at?: string;
}

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

  getMyParticipation: async (code: string, fingerprint?: string): Promise<ChatParticipation> => {
    const response = await api.get(`/api/chats/${code}/my-participation/`, {
      params: { fingerprint },
    });
    return response.data;
  },

  validateUsername: async (code: string, username: string, fingerprint?: string): Promise<{
    available: boolean;
    username: string;
    in_use_in_chat: boolean;
    reserved_by_other: boolean;
    has_reserved_badge: boolean;
    message: string;
  }> => {
    const response = await api.post(`/api/chats/${code}/validate-username/`, {
      username,
      fingerprint,
    });
    return response.data;
  },

  suggestUsername: async (code: string, fingerprint?: string): Promise<{
    username: string;
    remaining: number;
  }> => {
    const response = await api.post(`/api/chats/${code}/suggest-username/`, {
      fingerprint,
    });
    return response.data;
  },

  checkRateLimit: async (code: string, fingerprint?: string): Promise<{
    can_join: boolean;
    is_rate_limited: boolean;
    anonymous_count?: number;
    max_allowed?: number;
    existing_username?: string;
  }> => {
    const params = fingerprint ? { fingerprint } : {};
    const response = await api.get(`/api/chats/${code}/check-rate-limit/`, { params });
    return response.data;
  },

  joinChat: async (code: string, username: string, accessCode?: string, fingerprint?: string) => {
    const response = await api.post(`/api/chats/${code}/join/`, {
      username,
      access_code: accessCode,
      fingerprint,
    });

    // Store session token if provided
    if (response.data.session_token) {
      localStorage.setItem(`chat_session_${code}`, response.data.session_token);
    }

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
    // Support new Redis cache response format: { messages: [...], pinned_messages: [...], source: "redis" }
    // Fallback to old paginated format: { results: [...] }
    // Fallback to direct array: [...]
    return response.data.messages || response.data.results || response.data;
  },

  sendMessage: async (code: string, username: string, content: string): Promise<Message> => {
    // Get session token from localStorage
    const sessionToken = localStorage.getItem(`chat_session_${code}`);

    const response = await api.post(`/api/chats/${code}/messages/send/`, {
      username,
      content,
      session_token: sessionToken,
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
