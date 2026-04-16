/**
 * Format a chat-message timestamp for display in the bubble's bottom row.
 * "Today 3:42 PM" / "Yesterday 8:15 AM" / "Tue 11:00 AM" / "3/14 9:23 PM".
 *
 * Shared by MainChatView, StickySection, and MessagePreviewModal so the
 * timestamp formatting stays consistent across all message renderings.
 */
export function formatTimestamp(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const time = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

  const dateOnly = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const todayOnly = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayOnly = new Date(todayOnly);
  yesterdayOnly.setDate(yesterdayOnly.getDate() - 1);

  const daysDiff = Math.floor((todayOnly.getTime() - dateOnly.getTime()) / (1000 * 60 * 60 * 24));

  if (dateOnly.getTime() === todayOnly.getTime()) return `Today ${time}`;
  if (dateOnly.getTime() === yesterdayOnly.getTime()) return `Yesterday ${time}`;
  if (daysDiff < 7 && daysDiff > 0) {
    const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
    return `${dayName} ${time}`;
  }
  return `${date.getMonth() + 1}/${date.getDate()} ${time}`;
}
