/**
 * Username storage utility with layered fallback
 * Priority: localStorage → sessionStorage → fingerprint (if enabled)
 */

export class UsernameStorage {
  /**
   * Get username for a specific chat
   * Checks localStorage first, then sessionStorage
   */
  static getUsername(chatCode: string): string | null {
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

    return null;
  }

  /**
   * Save username for a specific chat
   * Saves to both localStorage and sessionStorage
   */
  static saveUsername(chatCode: string, username: string): void {
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
