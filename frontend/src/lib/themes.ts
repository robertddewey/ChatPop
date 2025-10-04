// Theme configuration for ChatPop
// Centralizes theme definitions and provides helper utilities

export type ThemeId = 'pink-dream' | 'ocean-blue' | 'dark-mode';
export type ThemeType = 'light' | 'dark';

export interface ThemeConfig {
  id: ThemeId;
  name: string;
  type: ThemeType;
  description?: string;
}

export const themes: Record<ThemeId, ThemeConfig> = {
  'pink-dream': {
    id: 'pink-dream',
    name: 'Pink Dream',
    type: 'light',
    description: 'Pink and rose gradients on a clean white background',
  },
  'ocean-blue': {
    id: 'ocean-blue',
    name: 'Ocean Blue',
    type: 'light',
    description: 'Blue and cyan gradients with a fresh, airy feel',
  },
  'dark-mode': {
    id: 'dark-mode',
    name: 'Dark Mode',
    type: 'dark',
    description: 'Cyan and yellow accents on a sleek dark background',
  },
};

// Helper to check if a theme is dark mode
export const isDarkTheme = (themeId: string | undefined): boolean => {
  if (!themeId) return false;
  const theme = themes[themeId as ThemeId];
  return theme?.type === 'dark';
};

// Get theme config by ID, with fallback
export const getTheme = (themeId: string | undefined): ThemeConfig => {
  return themes[(themeId as ThemeId)] || themes['pink-dream'];
};

// Default theme
export const DEFAULT_THEME: ThemeId = 'pink-dream';

// Legacy mapping for backward compatibility (URLs with old design1/2/3 and old theme names)
export const legacyThemeMapping: Record<string, ThemeId> = {
  'design1': 'pink-dream',
  'purple-dream': 'pink-dream',
  'midnight-rose': 'pink-dream',
  'design2': 'ocean-blue',
  'design3': 'dark-mode',
};

// Convert legacy theme ID to new ID
export const migrateLegacyTheme = (themeId: string | null): ThemeId => {
  if (!themeId) return DEFAULT_THEME;
  return legacyThemeMapping[themeId] || (themeId as ThemeId) || DEFAULT_THEME;
};
