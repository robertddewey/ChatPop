/**
 * Username storage utility with layered fallback
 * Priority: localStorage → sessionStorage → fingerprint (if enabled)
 */

import FingerprintJS from '@fingerprintjs/fingerprintjs';

// Use relative URL to leverage Next.js proxy (server.js proxies /api/ to backend)
const API_URL = '/api';

let fpPromise: Promise<any> | null = null;

/**
 * Get browser fingerprint (lazy loaded)
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
   * Checks localStorage → sessionStorage → fingerprint API (if enabled)
   *
   * @param chatCode - The chat room code
   * @param isLoggedIn - Whether the user is logged in (skip fingerprinting if true)
   * @returns Username or null if not found
   */
  static async getUsername(chatCode: string, isLoggedIn: boolean = false): Promise<string | null> {
    // Try localStorage first
    const localUsername = localStorage.getItem(`chat_username_${chatCode}`);
    if (localUsername) {
      // Also save to sessionStorage as backup
      sessionStorage.setItem(`chat_username_${chatCode}`, localUsername);
      return localUsername;
    }

    // Fallback to sessionStorage
    const sessionUsername = sessionStorage.getItem(`chat_username_${chatCode}`);
    if (sessionUsername) {
      // Restore to localStorage
      localStorage.setItem(`chat_username_${chatCode}`, sessionUsername);
      return sessionUsername;
    }

    // Skip fingerprinting for logged-in users
    if (isLoggedIn) {
      return null;
    }

    // Try fingerprint API (if enabled)
    try {
      const fingerprint = await getFingerprint();
      const response = await fetch(
        `${API_URL}/chats/${chatCode}/fingerprint-username/?fingerprint=${encodeURIComponent(fingerprint)}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.found && data.username) {
          // Save to localStorage and sessionStorage
          this.saveUsername(chatCode, data.username);
          return data.username;
        }
      }
      // If fingerprinting is disabled (503) or not found, return null
      return null;
    } catch (error) {
      console.warn('Failed to get username from fingerprint:', error);
      return null;
    }
  }

  /**
   * Save username for a specific chat
   * Saves to localStorage, sessionStorage, and fingerprint API (if enabled)
   *
   * @param chatCode - The chat room code
   * @param username - The username to save
   * @param isLoggedIn - Whether the user is logged in (skip fingerprinting if true)
   */
  static async saveUsername(chatCode: string, username: string, isLoggedIn: boolean = false): Promise<void> {
    // Always save to localStorage and sessionStorage
    localStorage.setItem(`chat_username_${chatCode}`, username);
    sessionStorage.setItem(`chat_username_${chatCode}`, username);

    // Skip fingerprinting for logged-in users
    if (isLoggedIn) {
      return;
    }

    // Also save to fingerprint API (if enabled)
    try {
      const fingerprint = await getFingerprint();
      await fetch(`${API_URL}/chats/${chatCode}/fingerprint-username/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          fingerprint,
          username,
        }),
      });
      // Silently fail if fingerprinting is disabled or fails
    } catch (error) {
      console.warn('Failed to save username to fingerprint:', error);
    }
  }

  /**
   * Clear username for a specific chat
   */
  static clearUsername(chatCode: string): void {
    localStorage.removeItem(`chat_username_${chatCode}`);
    sessionStorage.removeItem(`chat_username_${chatCode}`);
  }
}
