/**
 * Modal State Persistence
 *
 * Allows preserving modal state (results) across navigation so users can
 * go back to the modal with suggestions after visiting a chat room.
 *
 * Flow:
 * 1. User opens modal, gets results
 * 2. User clicks a suggestion → saveModalState() called → navigates to chat
 * 3. User clicks back → returns to home page
 * 4. Home page calls getModalState() → reopens modal with cached results
 */

const MODAL_STATE_KEY = 'chatpop_pending_modal';

export type ModalType = 'photo' | 'audio' | 'location';

export interface ModalState {
  type: ModalType;
  results: unknown;
  timestamp: number;
}

/**
 * Save modal state before navigating away.
 * Call this right before router.push() to a chat room.
 */
export function saveModalState(type: ModalType, results: unknown): void {
  const state: ModalState = {
    type,
    results,
    timestamp: Date.now(),
  };

  try {
    sessionStorage.setItem(MODAL_STATE_KEY, JSON.stringify(state));
    console.log(`📦 [ModalState] Saved ${type} modal state`);
  } catch (e) {
    console.warn('[ModalState] Failed to save state:', e);
  }
}

/**
 * Get pending modal state WITHOUT clearing it.
 * State persists until user explicitly closes the modal.
 * Returns null if no state or state is expired (>5 min old).
 */
export function getModalState(): ModalState | null {
  try {
    const raw = sessionStorage.getItem(MODAL_STATE_KEY);
    if (!raw) return null;

    const state: ModalState = JSON.parse(raw);

    // Check if state is too old (5 minutes)
    const age = Date.now() - state.timestamp;
    if (age > 5 * 60 * 1000) {
      console.log('[ModalState] State expired, clearing');
      sessionStorage.removeItem(MODAL_STATE_KEY);
      return null;
    }

    console.log(`📦 [ModalState] Retrieved ${state.type} modal state`);
    return state;
  } catch (e) {
    console.warn('[ModalState] Failed to get state:', e);
    return null;
  }
}

/**
 * Clear any pending modal state.
 * Call this when user manually closes a modal or navigates away intentionally.
 */
export function clearModalState(): void {
  try {
    sessionStorage.removeItem(MODAL_STATE_KEY);
  } catch (e) {
    // Ignore
  }
}

/**
 * Check if there's pending modal state without consuming it.
 */
export function hasModalState(): boolean {
  try {
    return sessionStorage.getItem(MODAL_STATE_KEY) !== null;
  } catch {
    return false;
  }
}

// ============================================================================
// Fresh Navigation Flag
// ============================================================================
// Prevents users from using browser forward button to return to chat pages
// they haven't joined. They must explicitly click a suggestion to navigate.

const FRESH_NAV_KEY = 'chatpop_fresh_navigation';

/**
 * Mark that we're doing a fresh navigation to a chat page.
 * Call this right before router.push() to a chat room.
 */
export function setFreshNavigation(): void {
  try {
    sessionStorage.setItem(FRESH_NAV_KEY, 'true');
  } catch {
    // Ignore
  }
}

/**
 * Check and consume the fresh navigation flag.
 * Returns true if this is a fresh navigation (from modal click).
 * Returns false if this is likely a forward navigation (browser forward button).
 */
export function consumeFreshNavigation(): boolean {
  try {
    const isFresh = sessionStorage.getItem(FRESH_NAV_KEY) === 'true';
    sessionStorage.removeItem(FRESH_NAV_KEY);
    return isFresh;
  } catch {
    return false;
  }
}

// ============================================================================
// Chat Page Visit Tracking
// ============================================================================
// Tracks whether a user has visited a chat page in this session.
// Used to detect forward navigation (vs direct URL access).

const VISITED_CHAT_PREFIX = 'chatpop_visited_chat_';

/**
 * Mark that user has visited a chat page.
 * Called when landing on chat page via valid navigation.
 */
export function markChatVisited(chatCode: string): void {
  try {
    sessionStorage.setItem(`${VISITED_CHAT_PREFIX}${chatCode}`, 'true');
  } catch {
    // Ignore
  }
}

/**
 * Check if user has previously visited this chat page in this session.
 */
export function hasChatBeenVisited(chatCode: string): boolean {
  try {
    return sessionStorage.getItem(`${VISITED_CHAT_PREFIX}${chatCode}`) === 'true';
  } catch {
    return false;
  }
}

/**
 * Clear the chat visited marker.
 * Called when user successfully joins the chat.
 */
export function clearChatVisited(chatCode: string): void {
  try {
    sessionStorage.removeItem(`${VISITED_CHAT_PREFIX}${chatCode}`);
  } catch {
    // Ignore
  }
}
