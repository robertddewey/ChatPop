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
  avatar_url: string | null;
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
  broadcast_icon_color: string;
  crown_icon_color: string;
  badge_icon_color: string;
  reply_icon_color: string;
  my_username: string;
  regular_username: string;
  host_username: string;
  my_host_username: string;
  pinned_username: string;
  sticky_host_username: string;
  sticky_pinned_username: string;
  my_timestamp: string;
  regular_timestamp: string;
  host_timestamp: string;
  pinned_timestamp: string;
  reply_preview_container: string;
  reply_preview_icon: string;
  reply_preview_username: string;
  reply_preview_content: string;
  reply_preview_close_button: string;
  reply_preview_close_icon: string;
  reaction_highlight_bg: string;
  reaction_highlight_border: string;
  reaction_highlight_text: string;
  // Component style overrides
  modal_styles: Record<string, string>;
  emoji_picker_styles: Record<string, string>;
  gift_styles: Record<string, string>;
  input_styles: Record<string, string>;
  video_player_styles: Record<string, string>;
  ui_styles: Record<string, string>;
  // Avatar settings
  avatar_size: string | null;
  avatar_border: string | null;
  avatar_spacing: string;
}

export interface ChatRoom {
  id: string;
  code: string;
  name: string;
  description: string;
  host: User;
  url: string;
  access_mode: 'public' | 'private';
  is_private?: boolean;
  voice_enabled: boolean;
  video_enabled: boolean;
  photo_enabled: boolean;
  theme: ChatTheme | null;
  theme_locked: boolean;
  message_count: number;
  is_active: boolean;
  created_at: string;
  has_back_room?: boolean;
}

export interface ReplyToMessage {
  id: string;
  username: string;
  content: string;
  message_type?: string;
  is_from_host: boolean;
  username_is_reserved: boolean;
  is_pinned: boolean;
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
  has_reacted: boolean;
}

export interface Message {
  id: string;
  chat_room: string;
  username: string;
  user: User | null;
  message_type: 'normal' | 'system' | 'gift';
  content: string;
  voice_url: string | null;
  voice_duration: number | null;
  voice_waveform: number[] | null;
  photo_url: string | null;
  photo_width: number | null;
  photo_height: number | null;
  video_url: string | null;
  video_duration: number | null;
  video_thumbnail_url: string | null;
  video_width: number | null;
  video_height: number | null;
  reply_to: string | null;
  reply_to_message: ReplyToMessage | null;
  is_pinned: boolean;
  pinned_at: string | null;
  sticky_until: string | null;
  pin_amount_paid: string;
  current_pin_amount: string;
  is_from_host: boolean;
  username_is_reserved: boolean;
  time_until_unpin: number | null;
  avatar_url: string;
  created_at: string;
  is_deleted: boolean;
  gift_recipient?: string | null;
  is_gift_acknowledged?: boolean;
  is_broadcast?: boolean;
  reactions?: ReactionSummary[]; // Top 3 reactions for display
}

export interface GiftNotification {
  id: string;
  gift_id: string;
  emoji: string;
  name: string;
  price_cents: number;
  sender_username: string;
  created_at: string;
}

export interface PhotoSuggestion {
  key: string;
  name: string;
  description: string;
  has_room: boolean;
  messages_24h: number;  // Total messages in last 24 hours
  messages_10min: number;  // Messages in last 10 minutes (for "active" indicator)
  source: string; // 'matched' | 'created' | 'proper_noun'
  usage_count: number;
  is_proper_noun: boolean;
}

export interface PhotoAnalysisResponse {
  cached: boolean;
  analysis: {
    id: string;
    suggestions: PhotoSuggestion[];
    username: string | null;
    created_at: string;
    updated_at: string;
    expires_at: string;
    is_expired: boolean;
    image_phash: string;
    file_hash: string;
    file_size: number;
    seed_suggestions: Array<{ name: string; key: string; description: string }>;
    selected_suggestion_code: string | null;
    selected_at: string | null;
  };
}

// API Functions
export const authApi = {
  register: async (data: { email: string; password: string; reserved_username?: string; fingerprint?: string; avatar_seed?: string }) => {
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

  checkUsername: async (username: string, fingerprint?: string): Promise<{ available: boolean; message: string }> => {
    const response = await api.get('/api/auth/check-username/', {
      params: { username, fingerprint },
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

export interface AnonymousParticipationInfo {
  username: string;
  avatar_url: string | null;
  first_joined_at: string;
}

export interface ChatParticipation {
  has_joined: boolean;
  username?: string;
  username_is_reserved?: boolean;
  avatar_url?: string | null;
  first_joined_at?: string;
  last_seen_at?: string;
  theme?: ChatTheme | null;
  is_blocked?: boolean;
  seen_intros?: Record<string, boolean>;
  is_anonymous_identity?: boolean;
  anonymous_participation?: AnonymousParticipationInfo;
}

/**
 * Build chat base URL.
 * All rooms use: /api/chats/{username}/{code}
 * - Manual rooms: username is the host's reserved_username
 * - AI/Discover rooms: username is 'discover' (system user)
 */
function buildChatUrl(code: string, roomUsername?: string): string {
  // Default to 'discover' for AI-generated rooms
  const username = roomUsername || 'discover';
  return `/api/chats/${username}/${code}`;
}

export const chatApi = {
  // Get chat configuration options
  getConfig: async (): Promise<{
    discovery_radius_options: number[];
  }> => {
    const response = await api.get('/api/chats/config/');
    return response.data;
  },

  createChat: async (data: {
    name: string;
    description?: string;
    access_mode: 'public' | 'private';
    access_code?: string;
    voice_enabled?: boolean;
    video_enabled?: boolean;
    photo_enabled?: boolean;
    latitude?: number;
    longitude?: number;
    discovery_radius_miles?: number;
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
    generation_remaining?: number;
    is_returning?: boolean;
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

  joinChat: async (code: string, username: string, accessCode?: string, fingerprint?: string, roomUsername?: string, avatarSeed?: string) => {
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/join/`, {
      username,
      access_code: accessCode,
      fingerprint,
      avatar_seed: avatarSeed,
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
  getMessages: async (code: string, roomUsername?: string, sessionToken?: string, filter?: string, filterUsername?: string): Promise<{ messages: Message[], pinnedMessages: Message[] }> => {
    const params: Record<string, string> = {};
    if (sessionToken) {
      params.session_token = sessionToken;
    }
    if (filter) {
      params.filter = filter;
      if (filterUsername) {
        params.filter_username = filterUsername;
      }
    }
    const response = await api.get(`${buildChatUrl(code, roomUsername)}/messages/`, { params });
    // Support new Redis cache response format: { messages: [...], pinned_messages: [...], source: "redis" }
    // Fallback to old paginated format: { results: [...] }
    // Fallback to direct array: [...]
    const messages = response.data.messages || response.data.results || response.data;
    const pinnedMessages = response.data.pinned_messages || [];
    return { messages, pinnedMessages };
  },

  getMessagesBefore: async (code: string, beforeTimestamp: number, limit: number = 50, roomUsername?: string, filter?: string, filterUsername?: string): Promise<{ messages: Message[], hasMore: boolean }> => {
    const params: Record<string, string | number> = {
      before: beforeTimestamp,
      limit
    };
    if (filter) {
      params.filter = filter;
      if (filterUsername) {
        params.filter_username = filterUsername;
      }
    }
    const response = await api.get(`${buildChatUrl(code, roomUsername)}/messages/`, { params });

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

  // Get pin requirements for a message (current pin value, minimum required, tiers, etc.)
  getPinRequirements: async (code: string, messageId: string, roomUsername?: string): Promise<{
    current_pin_cents: number;
    minimum_cents?: number;  // Legacy, deprecated
    required_cents?: number;  // Legacy, deprecated
    minimum_required_cents?: number;  // Total amount needed to win sticky
    minimum_add_cents?: number;  // For reclaim: minimum tier to ADD (additive)
    my_investment_cents?: number;  // User's existing investment (for reclaim)
    duration_minutes: number;
    tiers?: { amount_cents: number; duration_minutes: number }[];  // Available tiers
    is_current_sticky?: boolean;  // Is this message the current sticky holder
    is_outbid?: boolean;  // Was this message outbid but has time remaining (can reclaim)
    time_remaining_seconds?: number;  // Remaining time if outbid (for reclaim stacking)
  }> => {
    const response = await api.get(`${buildChatUrl(code, roomUsername)}/messages/${messageId}/pin/`);
    return response.data;
  },

  // Pin a message (or outbid existing pin)
  pinMessage: async (code: string, messageId: string, amountCents: number, roomUsername?: string): Promise<{
    success: boolean;
    message: string;
    sticky_until: string;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);

    const response = await api.post(`${buildChatUrl(code, roomUsername)}/messages/${messageId}/pin/`, {
      amount_cents: amountCents,
      session_token: sessionToken,
    });
    return response.data;
  },

  // Add to an existing pin (increase value without resetting timer)
  addToPin: async (code: string, messageId: string, amountCents: number, roomUsername?: string): Promise<{
    success: boolean;
    message: string;
    new_total_cents: number;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);

    const response = await api.post(`${buildChatUrl(code, roomUsername)}/messages/${messageId}/add-to-pin/`, {
      amount_cents: amountCents,
      session_token: sessionToken,
    });
    return response.data;
  },

  // Toggle broadcast on a message (host-only)
  broadcastMessage: async (code: string, messageId: string, roomUsername?: string): Promise<{
    success: boolean;
    is_broadcast: boolean;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/messages/${messageId}/broadcast/`, {
      session_token: sessionToken,
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

  uploadPhoto: async (code: string, photoFile: File, roomUsername?: string): Promise<{
    photo_url: string;
    width: number;
    height: number;
    storage_path: string;
    storage_type: string;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);

    const formData = new FormData();
    formData.append('photo', photoFile);
    formData.append('session_token', sessionToken || '');

    const response = await api.post(
      `${buildChatUrl(code, roomUsername)}/photo/upload/`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  uploadVideo: async (code: string, videoFile: File, roomUsername?: string): Promise<{
    video_url: string;
    duration: number;
    thumbnail_url: string;
    width: number | null;
    height: number | null;
    storage_path: string;
    storage_type: string;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);

    const formData = new FormData();
    formData.append('video', videoFile);
    formData.append('session_token', sessionToken || '');

    const response = await api.post(
      `${buildChatUrl(code, roomUsername)}/video/upload/`,
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

  getReactions: async (code: string, messageId: string, roomUsername?: string, sessionToken?: string): Promise<{
    reactions: MessageReaction[];
    summary: ReactionSummary[];
    total_count: number;
  }> => {
    const params: Record<string, string> = {};
    if (sessionToken) {
      params.session_token = sessionToken;
    }
    const response = await api.get(`${buildChatUrl(code, roomUsername)}/messages/${messageId}/reactions/`, { params });
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

  // Photo Analysis (Suggestion Matching)
  analyzePhoto: async (
    photo: File,
    fingerprint?: string,
    username?: string
  ): Promise<PhotoAnalysisResponse> => {
    const formData = new FormData();
    formData.append('image', photo); // Backend expects 'image', not 'photo'

    if (fingerprint) {
      formData.append('fingerprint', fingerprint);
    }

    if (username) {
      formData.append('username', username);
    }

    const response = await api.post('/api/media-analysis/photo/upload/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Create Chat from Photo Analysis
  createChatFromPhoto: async (data: {
    media_analysis_id: string;
    room_code: string;
  }): Promise<{
    created: boolean;
    chat_room: ChatRoom;
    message: string;
  }> => {
    const response = await api.post('/api/chats/create-from-photo/', data);
    return response.data;
  },

  // Create Chat from Location Analysis
  createChatFromLocation: async (data: {
    location_analysis_id: string;
    room_code: string;
  }): Promise<{
    created: boolean;
    chat_room: ChatRoom;
    message: string;
  }> => {
    const response = await api.post('/api/chats/create-from-location/', data);
    return response.data;
  },

  // Create Chat from Music Analysis
  createChatFromMusic: async (data: {
    music_analysis_id: string;
    room_code: string;
  }): Promise<{
    created: boolean;
    chat_room: ChatRoom;
    message: string;
  }> => {
    const response = await api.post('/api/chats/create-from-music/', data);
    return response.data;
  },
};

// Gift API
export const giftApi = {
  getCatalog: async (code: string, roomUsername?: string): Promise<{
    items: Array<{
      gift_id: string;
      emoji: string;
      name: string;
      price_cents: number;
      category: string;
      sort_order: number;
    }>;
    bulk_action_threshold?: number;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);
    const response = await api.get(`${buildChatUrl(code, roomUsername)}/gifts/catalog/`, {
      params: { session_token: sessionToken },
    });
    return response.data;
  },

  sendGift: async (code: string, giftId: string, recipientUsername: string, roomUsername?: string): Promise<{
    success: boolean;
    gift_id: string;
    message_id: string;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/gifts/send/`, {
      gift_id: giftId,
      recipient_username: recipientUsername,
      session_token: sessionToken,
    });
    return response.data;
  },

  acknowledgeGift: async (code: string, giftId: string, thank: boolean = false, roomUsername?: string): Promise<{
    success: boolean;
    remaining_count: number;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/gifts/acknowledge/`, {
      gift_id: giftId,
      thank,
      session_token: sessionToken,
    });
    return response.data;
  },

  acknowledgeAllGifts: async (code: string, thank: boolean = false, roomUsername?: string): Promise<{
    success: boolean;
    remaining_count: number;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/gifts/acknowledge/`, {
      acknowledge_all: true,
      thank,
      session_token: sessionToken,
    });
    return response.data;
  },

  acknowledgeGiftByMessage: async (code: string, messageId: string, roomUsername?: string): Promise<{
    success: boolean;
    remaining_count: number;
  }> => {
    const sessionToken = localStorage.getItem(`chat_session_${code}`);
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/gifts/acknowledge/`, {
      message_id: messageId,
      thank: true,
      session_token: sessionToken,
    });
    return response.data;
  },

  dismissIntro: async (code: string, key: string, fingerprint?: string, roomUsername?: string): Promise<{ success: boolean }> => {
    const response = await api.post(`${buildChatUrl(code, roomUsername)}/intros/${key}/dismiss/`, {
      fingerprint,
    });
    return response.data;
  },
};

// Location API Types
export interface LocationSuggestion {
  name: string;
  key: string;
  type: 'city' | 'neighborhood' | 'county' | 'metro' | 'venue' | 'landmark' | 'restaurant' | 'bar' | 'cafe' | 'park';
  description: string;
  address?: string;
  rating?: number;
  has_room?: boolean;
  messages_24h?: number;  // Total messages in last 24 hours
  messages_10min?: number;  // Messages in last 10 minutes (for "active" indicator)
}

export interface LocationAnalysisResponse {
  success: boolean;
  id: string;
  cached: boolean;
  cache_source: 'redis' | 'postgresql' | 'api';
  location: {
    city: string | null;
    neighborhood: string | null;
    county: string | null;
    metro_area: string | null;
    state: string | null;
    geohash: string;
  };
  suggestions: LocationSuggestion[];
  best_guess: LocationSuggestion | null;
}

// Nearby Discoverable Chats Types
export interface NearbyDiscoverableChat {
  id: string;
  code: string;
  name: string;
  description: string;
  url: string;
  access_mode: 'public' | 'private';
  host_username: string;
  messages_24h: number;
  messages_10min: number;
  distance_miles: number;
}

export interface NearbyDiscoverableChatsResponse {
  chats: NearbyDiscoverableChat[];
  total_count: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export const locationApi = {
  // Get location-based chat suggestions from coordinates
  getSuggestions: async (
    latitude: number,
    longitude: number,
    fingerprint?: string
  ): Promise<LocationAnalysisResponse> => {
    const response = await api.post('/api/media-analysis/location/suggest/', {
      latitude,
      longitude,
      fingerprint,
    });
    return response.data;
  },

  // Get a specific location analysis by ID
  getAnalysis: async (id: string): Promise<LocationAnalysisResponse> => {
    const response = await api.get(`/api/media-analysis/location/${id}/`);
    return response.data;
  },

  // Get recent location analyses for current user
  getRecent: async (limit: number = 10): Promise<Array<{
    id: string;
    city: string;
    neighborhood: string;
    geohash: string;
    created_at: string;
  }>> => {
    const response = await api.get('/api/media-analysis/location/recent/', {
      params: { limit },
    });
    return response.data;
  },

  // Create chat room from location suggestion
  createChatFromLocation: async (data: {
    location_analysis_id: string;
    suggestion_key: string;
  }): Promise<{
    created: boolean;
    chat_room: ChatRoom;
    message: string;
  }> => {
    const response = await api.post('/api/chats/create-from-location/', data);
    return response.data;
  },

  // Get nearby discoverable chats
  getNearbyDiscoverableChats: async (params: {
    latitude: number;
    longitude: number;
    radius: number;
    offset?: number;
    limit?: number;
  }): Promise<NearbyDiscoverableChatsResponse> => {
    const response = await api.post('/api/chats/nearby/', {
      latitude: params.latitude,
      longitude: params.longitude,
      radius: params.radius,
      offset: params.offset ?? 0,
      limit: params.limit ?? 20,
    });
    return response.data;
  },
};

// Activity Polling Types
export interface ActivityPollResponse {
  poll_interval_seconds: number;
  activity: {
    [roomCode: string]: {
      has_room: boolean;
      messages_24h: number;
      messages_10min: number;
    };
  };
}

// Activity Polling API
export const activityApi = {
  // Poll activity for multiple room codes
  poll: async (roomCodes: string[]): Promise<ActivityPollResponse> => {
    const response = await api.get('/api/media-analysis/activity/poll/', {
      params: { room_codes: roomCodes.join(',') },
    });
    return response.data;
  },
};

// Admin API Types
export interface SiteBan {
  id: string;
  banned_user: string | null;
  banned_user_id: string | null;
  banned_ip_address: string | null;
  banned_fingerprint: string | null;
  banned_fingerprint_full: string | null;
  reason: string;
  banned_by: string | null;
  created_at: string;
  expires_at: string | null;
  is_active: boolean;
  is_expired: boolean;
}

export interface AdminChatDetail {
  chat_room: ChatRoom;
  chat_url: string;
  is_ai_generated: boolean;
}

export interface AdminMessageList {
  messages: Message[];
  count: number;
}

// Admin API (staff only)
export const adminApi = {
  // Get chat room details by UUID
  getChatDetail: async (roomId: string): Promise<AdminChatDetail> => {
    const response = await api.get(`/api/chats/admin/${roomId}/`);
    return response.data;
  },

  // Get messages for a chat room
  getMessages: async (roomId: string, limit = 100, offset = 0): Promise<AdminMessageList> => {
    const response = await api.get(`/api/chats/admin/${roomId}/messages/`, {
      params: { limit, offset },
    });
    return response.data;
  },

  // Delete a message
  deleteMessage: async (roomId: string, messageId: string): Promise<{
    success: boolean;
    message: string;
    deleted_by: string;
  }> => {
    const response = await api.post(`/api/chats/admin/${roomId}/messages/${messageId}/delete/`);
    return response.data;
  },

  // Unpin a message
  unpinMessage: async (roomId: string, messageId: string): Promise<{
    success: boolean;
    message: string;
    unpinned_by: string;
  }> => {
    const response = await api.post(`/api/chats/admin/${roomId}/messages/${messageId}/unpin/`);
    return response.data;
  },

  // List site bans
  getSiteBans: async (activeOnly = false): Promise<{
    bans: SiteBan[];
    count: number;
  }> => {
    const response = await api.get('/api/chats/admin/site-bans/', {
      params: { active_only: activeOnly },
    });
    return response.data;
  },

  // Create a site ban
  createSiteBan: async (data: {
    user_id?: string;
    username?: string;
    ip_address?: string;
    fingerprint?: string;
    reason: string;
    expires_at?: string;
  }): Promise<{
    success: boolean;
    ban_id: string;
    message: string;
    kicked_immediately: boolean;
  }> => {
    const response = await api.post('/api/chats/admin/site-bans/create/', data);
    return response.data;
  },

  // Revoke a site ban
  revokeSiteBan: async (banId: string): Promise<{
    success: boolean;
    message: string;
  }> => {
    const response = await api.post(`/api/chats/admin/site-bans/${banId}/revoke/`);
    return response.data;
  },

  // Create a chat-specific ban
  createChatBan: async (roomId: string, data: {
    username?: string;
    fingerprint?: string;
    reason?: string;
  }): Promise<{
    success: boolean;
    message: string;
    block_id?: string;
    already_banned?: boolean;
    banned_by?: string;
  }> => {
    const response = await api.post(`/api/chats/admin/${roomId}/ban/`, data);
    return response.data;
  },
};

// Back Room API (for premium back room feature - stub for now)
export interface BackRoom {
  id: string;
  chat_room: string;
  name: string;
  description: string;
  price_per_seat: number;
  max_seats: number;
  seats_available: number;
  is_full: boolean;
  is_active: boolean;
}

export const backRoomApi = {
  getBackRoom: async (code: string): Promise<BackRoom | null> => {
    // TODO: Implement back room API when backend is ready
    console.warn('backRoomApi.getBackRoom is not yet implemented');
    return null;
  },
};

// Dev-only API endpoints (only accessible when backend DEBUG=True)
export interface DevRecentPhoto {
  id: string;
  image_url: string;
  created_at: string;
}

export const devApi = {
  // Get recent photos for dev photo picker
  getRecentPhotos: async (): Promise<DevRecentPhoto[]> => {
    const response = await api.get('/api/media-analysis/photo/dev/recent-photos/');
    return response.data;
  },
};
