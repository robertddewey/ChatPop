/**
 * Shared validation utilities for usernames
 */

export interface UsernameValidationResult {
  isValid: boolean;
  error?: string;
}

/**
 * Validate username format
 *
 * Rules:
 * - Minimum length: 5 characters
 * - Maximum length: 15 characters
 * - Allowed characters: letters (a-z, A-Z), numbers (0-9), and underscores (_)
 * - No spaces allowed
 * - Case is preserved but doesn't count toward uniqueness
 */
export function validateUsername(username: string): UsernameValidationResult {
  if (!username || username.trim().length === 0) {
    return {
      isValid: false,
      error: 'Username cannot be empty',
    };
  }

  const trimmed = username.trim();

  if (trimmed.length < 5) {
    return {
      isValid: false,
      error: 'Username must be at least 5 characters long',
    };
  }

  if (trimmed.length > 15) {
    return {
      isValid: false,
      error: 'Username must be at most 15 characters long',
    };
  }

  // Check allowed characters (letters, numbers, underscores only)
  const usernameRegex = /^[a-zA-Z0-9_]+$/;
  if (!usernameRegex.test(trimmed)) {
    return {
      isValid: false,
      error: 'Username can only contain letters, numbers, and underscores (no spaces)',
    };
  }

  return {
    isValid: true,
  };
}
