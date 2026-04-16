'use client';

/**
 * Small inline "pill" badges that appear next to usernames in the chat.
 * Extracted from MainChatView so they can be reused by MessageBubbleContent
 * (timeline + popup share the exact same rendering).
 */

import React from 'react';
import { Ban } from 'lucide-react';

/** Shown next to the current user's own username. */
export function YouPill({ className }: { className?: string }) {
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full leading-none ${
      className || 'bg-white/10 text-zinc-400'
    }`}>you</span>
  );
}

/** Shown next to host usernames. Hidden on small screens elsewhere by Tailwind responsive prefixes. */
export function HostPill({ color }: { color?: string }) {
  const c = color || '#2dd4bf';
  return (
    <span
      className="text-[10px] font-medium px-1.5 py-0.5 rounded-full leading-none"
      style={{ backgroundColor: `${c}20`, color: c }}
    >host</span>
  );
}

/** Shown next to spotlighted users. Responsive-hidden on mobile. */
export function SpotlightPill({ color }: { color?: string }) {
  const c = color || '#facc15';
  return (
    <span
      className="hidden sm:inline text-[10px] font-medium px-1.5 py-0.5 rounded-full leading-none"
      style={{ backgroundColor: `${c}20`, color: c }}
    >spotlight</span>
  );
}

/** Shown next to banned users. Responsive-hidden on mobile. */
export function BannedPill() {
  return (
    <span
      className="hidden sm:inline-flex text-[10px] font-medium px-1.5 py-0.5 rounded-full leading-none items-center gap-0.5"
      style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#ef4444' }}
    ><Ban size={9} />banned</span>
  );
}
