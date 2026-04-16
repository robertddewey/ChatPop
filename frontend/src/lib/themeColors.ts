/**
 * Theme color utilities — shared by MainChatView, MessageBubbleContent,
 * and any other component that needs to convert Tailwind class strings
 * to inline style hex values for use with `style={{ color: ... }}`.
 *
 * Why: theme classes are stored as strings in the database (Tailwind class
 * names) but icons/SVGs need a real color value via inline style.
 */

// Legacy lookup table — small set of frequently-used theme classes mapped
// directly to hex. Checked first by getTextColor / getIconColor.
const tailwindColors: Record<string, string> = {
  'text-amber-400': '#fbbf24',
  'text-teal-400': '#2dd4bf',
  'text-emerald-400': '#34d399',
  'text-emerald-300': '#6ee7b7',
  'text-cyan-400': '#22d3ee',
  'text-blue-500': '#3b82f6',
  'text-yellow-400': '#facc15',
  'text-white': '#ffffff',
  'text-gray-400': '#9ca3af',
  'text-red-500': '#ef4444',
  'text-purple-400': '#c084fc',
};

// Comprehensive Tailwind color palette for parsing arbitrary text-{color}-{shade}
// classes that aren't in the legacy table.
const tailwindColorValues: Record<string, Record<number, string>> = {
  'red':     { 50: '#fef2f2', 100: '#fee2e2', 200: '#fecaca', 300: '#fca5a5', 400: '#f87171', 500: '#ef4444', 600: '#dc2626', 700: '#b91c1c', 800: '#991b1b', 900: '#7f1d1d' },
  'blue':    { 50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd', 400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a' },
  'green':   { 50: '#f0fdf4', 100: '#dcfce7', 200: '#bbf7d0', 300: '#86efac', 400: '#4ade80', 500: '#22c55e', 600: '#16a34a', 700: '#15803d', 800: '#166534', 900: '#14532d' },
  'yellow':  { 50: '#fefce8', 100: '#fef9c3', 200: '#fef08a', 300: '#fde047', 400: '#facc15', 500: '#eab308', 600: '#ca8a04', 700: '#a16207', 800: '#854d0e', 900: '#713f12' },
  'purple':  { 50: '#faf5ff', 100: '#f3e8ff', 200: '#e9d5ff', 300: '#d8b4fe', 400: '#c084fc', 500: '#a855f7', 600: '#9333ea', 700: '#7e22ce', 800: '#6b21a8', 900: '#581c87' },
  'pink':    { 50: '#fdf2f8', 100: '#fce7f3', 200: '#fbcfe8', 300: '#f9a8d4', 400: '#f472b6', 500: '#ec4899', 600: '#db2777', 700: '#be185d', 800: '#9d174d', 900: '#831843' },
  'gray':    { 50: '#f9fafb', 100: '#f3f4f6', 200: '#e5e7eb', 300: '#d1d5db', 400: '#9ca3af', 500: '#6b7280', 600: '#4b5563', 700: '#374151', 800: '#1f2937', 900: '#111827' },
  'zinc':    { 50: '#fafafa', 100: '#f4f4f5', 200: '#e4e4e7', 300: '#d4d4d8', 400: '#a1a1aa', 500: '#71717a', 600: '#52525b', 700: '#3f3f46', 800: '#27272a', 900: '#18181b' },
  'cyan':    { 50: '#ecfeff', 100: '#cffafe', 200: '#a5f3fc', 300: '#67e8f9', 400: '#22d3ee', 500: '#06b6d4', 600: '#0891b2', 700: '#0e7490', 800: '#155e75', 900: '#164e63' },
  'teal':    { 50: '#f0fdfa', 100: '#ccfbf1', 200: '#99f6e4', 300: '#5eead4', 400: '#2dd4bf', 500: '#14b8a6', 600: '#0d9488', 700: '#0f766e', 800: '#115e59', 900: '#134e4a' },
  'emerald': { 50: '#ecfdf5', 100: '#d1fae5', 200: '#a7f3d0', 300: '#6ee7b7', 400: '#34d399', 500: '#10b981', 600: '#059669', 700: '#047857', 800: '#065f46', 900: '#064e3b' },
  'amber':   { 50: '#fffbeb', 100: '#fef3c7', 200: '#fde68a', 300: '#fcd34d', 400: '#fbbf24', 500: '#f59e0b', 600: '#d97706', 700: '#b45309', 800: '#92400e', 900: '#78350f' },
  'white':   { 500: '#ffffff' },
};

/** Convert a Tailwind icon class (e.g. "text-amber-400") to a hex value. */
export function getIconColor(tailwindClass: string | undefined): string | undefined {
  if (!tailwindClass) return undefined;
  return tailwindColors[tailwindClass.trim()];
}

/**
 * Extract a text color from a Tailwind class string, handling space-separated
 * classes ("text-xs font-semibold text-white") and `!` modifiers
 * ("text-xs !text-white opacity-60").
 */
export function getTextColor(classString: string | undefined): string | undefined {
  if (!classString) return undefined;

  for (const cls of classString.split(' ')) {
    const cleanClass = cls.replace(/^!/, '').replace(/\\/g, '');

    if (tailwindColors[cleanClass]) return tailwindColors[cleanClass];

    const match = cleanClass.match(/^text-([a-z]+)-(\d+)$/);
    if (match) {
      const [, colorName, shade] = match;
      const palette = tailwindColorValues[colorName];
      if (palette && palette[parseInt(shade)]) return palette[parseInt(shade)];
    }

    if (cleanClass === 'text-white') return '#ffffff';
    if (cleanClass === 'text-black') return '#000000';
  }
  return undefined;
}
