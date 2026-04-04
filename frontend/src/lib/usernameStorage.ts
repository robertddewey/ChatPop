/**
 * Username storage utility with layered fallback
 * Priority: localStorage → sessionStorage
 * Fingerprint is only used for ban enforcement (collected at join time via getFingerprint)
 */

import FingerprintJS from '@fingerprintjs/fingerprintjs';

let fpPromise: ReturnType<typeof FingerprintJS.load> | null = null;

/**
 * Get browser fingerprint (lazy loaded).
 * Used only for ban enforcement data collection at join time.
 */
export async function getFingerprint(): Promise<string> {
  if (!fpPromise) {
    fpPromise = FingerprintJS.load();
  }
  const fp = await fpPromise;
  const result = await fp.get();
  return result.visitorId;
}

export class UsernameStorage {
  /**
   * Get username for a specific chat
   * Checks localStorage → sessionStorage
   */
  static async getUsername(chatCode: string): Promise<string | null> {
    // Try localStorage first
    const localUsername = localStorage.getItem(`chat_username_${chatCode}`);
    if (localUsername) {
      sessionStorage.setItem(`chat_username_${chatCode}`, localUsername);
      return localUsername;
    }

    // Fallback to sessionStorage
    const sessionUsername = sessionStorage.getItem(`chat_username_${chatCode}`);
    if (sessionUsername) {
      localStorage.setItem(`chat_username_${chatCode}`, sessionUsername);
      return sessionUsername;
    }

    return null;
  }

  /**
   * Save username for a specific chat
   * Saves to localStorage and sessionStorage
   */
  static async saveUsername(chatCode: string, username: string, isLoggedIn: boolean = false): Promise<void> {
    localStorage.setItem(`chat_username_${chatCode}`, username);
    sessionStorage.setItem(`chat_username_${chatCode}`, username);
  }

  /**
   * Clear username for a specific chat
   */
  static clearUsername(chatCode: string): void {
    localStorage.removeItem(`chat_username_${chatCode}`);
    sessionStorage.removeItem(`chat_username_${chatCode}`);
  }
}
