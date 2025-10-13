/**
 * Client-side muted users management
 *
 * This module provides utilities for managing muted users in the frontend.
 * The mute list is fetched from the backend API and cached locally.
 *
 * IMPORTANT: The backend filters message history based on the user's mute list,
 * so muted messages will not appear after server restarts or page refreshes.
 * This client-side filtering is for real-time WebSocket messages only.
 */

export interface MutedUser {
  id: string;
  username: string;
  blocked_at: string;
}

/**
 * Get the list of muted users from the backend API
 * Only works for authenticated users
 */
export async function getMutedUsers(): Promise<MutedUser[]> {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    return [];
  }

  try {
    const response = await fetch('https://localhost:9000/api/chats/user-blocks/', {
      headers: {
        'Authorization': `Token ${token}`,
      },
    });

    if (!response.ok) {
      console.error('Failed to fetch muted users:', response.status);
      return [];
    }

    const data = await response.json();
    return data.blocked_users || [];
  } catch (error) {
    console.error('Error fetching muted users:', error);
    return [];
  }
}

/**
 * Get just the usernames of muted users (for filtering)
 */
export async function getMutedUsernames(): Promise<string[]> {
  const mutedUsers = await getMutedUsers();
  return mutedUsers.map(user => user.username);
}

/**
 * Check if a username is muted
 */
export async function isUserMuted(username: string): Promise<boolean> {
  const mutedUsernames = await getMutedUsernames();
  return mutedUsernames.includes(username);
}
