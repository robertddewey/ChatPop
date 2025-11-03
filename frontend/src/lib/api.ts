import axios from 'axios';

// Use relative URLs to leverage Next.js proxy (server.js proxies /api/ and /media/ to backend)
// This allows the app to work from both localhost and network IP addresses
const API_BASE_URL = '';

// Helper function to get CSRF token from cookies
function getCsrfToken(): string | null {
  const name = 'csrftoken';
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
}

// Create axios instance
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Send cookies with requests
});

// Add auth token and CSRF token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }

  // Add CSRF token for state-changing requests (POST, PUT, PATCH, DELETE)
  const csrfToken = getCsrfToken();
  if (csrfToken && config.method && ['post', 'put', 'patch', 'delete'].includes(config.method.toLowerCase())) {
    config.headers['X-CSRFToken'] = csrfToken;
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

export interface ChatTheme {
  theme_id: string;
  name: string;
  is_dark_mode: boolean;
  theme_color: {
    light: string;
    dark: string;
  };
  container: string;
  header: string;
  header_title: string;
  header_title_fade: string;
  header_subtitle: string;
  sticky_section: string;
  messages_area: string;
  messages_area_container: string;
  messages_area_bg: string;
  host_message: string;
  sticky_host_message: string;
  host_text: string;
  host_message_fade: string;
  pinned_message: string;
  sticky_pinned_message: string;
  pinned_text: string;
  pinned_message_fade: string;
  regular_message: string;
  regular_text: string;
  my_message: string;
  my_text: string;
  voice_message_styles: {
    containerBg?: string;
    playButton?: string;
    playIconColor?: string;
    waveformActive?: string;
    waveformInactive?: string;
    durationTextColor?: string;
  };
  my_voice_message_styles: {
    containerBg?: string;
    playButton?: string;
    playIconColor?: string;
    waveformActive?: string;
    waveformInactive?: string;
    durationTextColor?: string;
  };
  host_voice_message_styles: {
    containerBg?: string;
    playButton?: string;
    playIconColor?: string;
    waveformActive?: string;
    waveformInactive?: string;
    durationTextColor?: string;
  };
  pinned_voice_message_styles: {
    containerBg?: string;
    playButton?: string;
    playIconColor?: string;
    waveformActive?: string;
    waveformInactive?: string;
    durationTextColor?: string;
  };
  filter_button_active: string;
  filter_button_inactive: string;
  input_area: string;
  input_field: string;
  pin_icon_color: string;
  crown_icon_color: string;
  badge_icon_color: string;
  reply_icon_color: string;
  my_username: string;
  regular_username: string;
  host_username: string;
  pinned_username: string;
  my_timestamp: string;
  regular_timestamp: string;
  host_timestamp: string;
  pinned_timestamp: string;
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
  theme: ChatTheme | null;
  theme_locked: boolean;
  message_count: number;
  is_active: boolean;
  created_at: string;
}

export interface ReplyToMessage {
  id: string;
  username: string;
  content: string;
  is_from_host: boolean;
}

export interface MessageReaction {
  id: string;
  message: string;
  emoji: string;
  user: User | null;
  fingerprint: string | null;
  username: string;
  created_at: string;
}

export interface ReactionSummary {
  emoji: string;
  count: number;
  users: string[];
}

export interface Message {
  id: string;
  chat_room: string;
  username: string;
  user: User | null;
  message_type: 'normal' | 'host' | 'system';
  content: string;
  voice_url: string | null;
  voice_duration: number | null;
  voice_waveform: number[] | null;
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
  reactions?: ReactionSummary[]; // Top 3 reactions for display
}

// API Functions
export const authApi = {
  register: async (data: { email: string; password: string; reserved_username?: string; fingerprint?: string }) => {
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

  suggestUsername: async (fingerprint?: string): Promise<{ username: string; remaining_attempts?: number; is_rotating?: boolean }> => {
    const response = await api.post('/api/auth/suggest-username/', {
      fingerprint,
    });
    return response.data;
  },
};

export interface ChatParticipation {
  has_joined: boolean;
  username?: string;
  username_is_reserved?: boolean;
  first_joined_at?: string;
  last_seen_at?: string;
  theme?: ChatTheme | null;
  is_blocked?: boolean;
}

/**
 * Build chat base URL based on room type:
 * - Manual rooms (with username): /api/chats/{username}/{code}
 * - AI rooms (discover): /api/chats/discover/{code}
 */
function buildChatUrl(code: string, roomUsername?: string): string {
  if (roomUsername) {
    return `/api/chats/${roomUsername}/${code}`;
  }
  return `/api/chats/discover/${code}`;
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

  getChatByCode: async (code: string, roomUsername?: string): Promise<ChatRoom> => {
    const response = await api.get(`${buildChatUrl(code, roomUsername)}/`);
    return response.data;
  },

  getMyParticipation: async (code: string, fingerprint?: string, roomUsername?: string): Promise<ChatParticipation> => {
    const response = await api.get(`${buildChatUrl(code, roomUsername)}/my-participation/`, {
      params: { fingerprint },
    });
    return response.data;
  },

  validateUsername: async (code: string, username: string, fingerprint?: string, roomUsername?: string): Promise<{
    available: boolean;
    username: string;
    in_use_in_chat: boolean;
    reserved_by_other: boolean;
    has_reserved_badge: boolean;
    message: string;
  }> => {
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/validate-username/`, {
      username,
      fingerprint,
    });
    return response.data;
  },

  suggestUsername: async (code: string, fingerprint?: string, roomUsername?: string): Promise<{
    username: string;
    remaining: number;
  }> => {
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/suggest-username/`, {
      fingerprint,
    });
    return response.data;
  },

  checkRateLimit: async (code: string, fingerprint?: string, roomUsername?: string): Promise<{
    can_join: boolean;
    is_rate_limited: boolean;
    anonymous_count?: number;
    max_allowed?: number;
    existing_username?: string;
  }> => {
    const params = fingerprint ? { fingerprint } : {};
    const response = await api.get(`${buildChatUrl(code, roomUsername)}/check-rate-limit/`, { params });
    return response.data;
  },

  joinChat: async (code: string, username: string, accessCode?: string, fingerprint?: string, roomUsername?: string) => {
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/join/`, {
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
    theme_id?: string;
  }, roomUsername?: string): Promise<ChatRoom> => {
    const response = await api.put(`${buildChatUrl(code, roomUsername)}/update/`, data);
    return response.data;
  },

  updateMyTheme: async (code: string, themeId: string, fingerprint?: string, roomUsername?: string): Promise<{ success: boolean; theme: ChatTheme | null }> => {
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/update-my-theme/`, {
      theme_id: themeId,
      fingerprint,
    });
    return response.data;
  },
};

export const messageApi = {
  getMessages: async (code: string, roomUsername?: string): Promise<Message[]> => {
    const response = await api.get(`${buildChatUrl(code, roomUsername)}/messages/`);
    // Support new Redis cache response format: { messages: [...], pinned_messages: [...], source: "redis" }
    // Fallback to old paginated format: { results: [...] }
    // Fallback to direct array: [...]
    return response.data.messages || response.data.results || response.data;
  },

  getMessagesBefore: async (code: string, beforeTimestamp: number, limit: number = 50, roomUsername?: string): Promise<{ messages: Message[], hasMore: boolean }> => {
    const response = await api.get(`${buildChatUrl(code, roomUsername)}/messages/`, {
      params: {
        before: beforeTimestamp,
        limit
      }
    });

    const messages = response.data.messages || response.data.results || response.data;
    // Keep loading as long as we're getting messages back
    // Only stop when the API returns an empty array (reached the oldest message)
    const hasMore = messages.length > 0;

    return { messages, hasMore };
  },

  sendMessage: async (code: string, username: string, content: string, roomUsername?: string): Promise<Message> => {
    // Get session token from localStorage
    const sessionToken = localStorage.getItem(`chat_session_${code}`);

    const response = await api.post(`${buildChatUrl(code, roomUsername)}/messages/send/`, {
      username,
      content,
      session_token: sessionToken,
    });
    return response.data;
  },

  pinMessage: async (code: string, messageId: string, amount: number, duration_minutes: number = 60, roomUsername?: string) => {
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/messages/${messageId}/pin/`, {
      amount,
      duration_minutes,
    });
    return response.data;
  },

  uploadVoiceMessage: async (code: string, audioBlob: Blob, username: string, roomUsername?: string): Promise<{ voice_url: string; storage_path: string; storage_type: string }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);

    const formData = new FormData();
    formData.append('voice_message', audioBlob, 'voice.webm');
    formData.append('session_token', sessionToken || '');

    const response = await api.post(
      `${buildChatUrl(code, roomUsername)}/voice/upload/`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  // Reactions
  toggleReaction: async (code: string, messageId: string, emoji: string, username: string, fingerprint?: string, roomUsername?: string): Promise<{
    action: 'added' | 'removed' | 'updated';
    message: string;
    emoji: string;
    reaction: MessageReaction | null;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);

    const response = await api.post(`${buildChatUrl(code, roomUsername)}/messages/${messageId}/react/`, {
      emoji,
      session_token: sessionToken,
      username,
      fingerprint,
    });
    return response.data;
  },

  getReactions: async (code: string, messageId: string, roomUsername?: string): Promise<{
    reactions: MessageReaction[];
    summary: ReactionSummary[];
    total_count: number;
  }> => {
    const response = await api.get(`${buildChatUrl(code, roomUsername)}/messages/${messageId}/reactions/`);
    return response.data;
  },

  blockUser: async (code: string, data: {
    blocked_username?: string;
    blocked_fingerprint?: string;
    blocked_user_id?: number;
  }, roomUsername?: string) => {
    // Get session token from localStorage (required for host verification)
    const sessionToken = localStorage.getItem(`chat_session_${code}`);

    const response = await api.post(`${buildChatUrl(code, roomUsername)}/block-user/`, {
      ...data,
      session_token: sessionToken,
    });
    return response.data;
  },

  deleteMessage: async (code: string, messageId: string, roomUsername?: string): Promise<{
    success: boolean;
    message: string;
    message_id: string;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);

    const response = await api.post(`${buildChatUrl(code, roomUsername)}/messages/${messageId}/delete/`, {
      session_token: sessionToken,
    });
    return response.data;
  },

  // User-to-User Blocking (registered users only, site-wide)
  blockUserSiteWide: async (username: string): Promise<{
    success: boolean;
    message: string;
    created: boolean;
    block_id: string;
  }> => {
    const response = await api.post('/api/chats/user-blocks/block/', {
      username,
    });
    return response.data;
  },

  unblockUserSiteWide: async (username: string): Promise<{
    success: boolean;
    message: string;
  }> => {
    const response = await api.post('/api/chats/user-blocks/unblock/', {
      username,
    });
    return response.data;
  },

  getBlockedUsers: async (): Promise<{
    blocked_users: Array<{
      id: string;
      username: string;
      blocked_at: string;
    }>;
    count: number;
  }> => {
    const response = await api.get('/api/chats/user-blocks/');
    return response.data;
  },

  // Photo Analysis (Chat Generation)
  analyzePhoto: async (photo: File): Promise<{
    suggestions: Array<{
      name: string;
      description: string;
      theme_id: string;
    }>;
  }> => {
    const formData = new FormData();
    formData.append('photo', photo);

    const response = await api.post('/api/chats/analyze-photo/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Create Chat from Photo Analysis
  createChatFromPhoto: async (data: {
    photo_analysis_id: string;
    suggestion_index: number;
  }): Promise<{
    created: boolean;
    chat_room: ChatRoom;
    message: string;
  }> => {
    const response = await api.post('/api/chats/create-from-photo/', data);
    return response.data;
  },
};

