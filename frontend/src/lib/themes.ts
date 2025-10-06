// Theme configuration for ChatPop
// Centralizes theme definitions and provides helper utilities

export type ThemeId = 'dark-mode';
export type ThemeType = 'dark';

export interface ThemeConfig {
  id: ThemeId;
  name: string;
  type: ThemeType;
  description?: string;
}

export const themes: Record<ThemeId, ThemeConfig> = {
  'dark-mode': {
    id: 'dark-mode',
    name: 'Dark Mode',
    type: 'dark',
    description: 'Cyan and yellow accents on a sleek dark background',
  },
};

// Helper to check if a theme is dark mode
export const isDarkTheme = (themeId: string | undefined): boolean => {
  // Always return true since dark-mode is the only theme
  return true;
};

// Get theme config by ID, with fallback
export const getTheme = (themeId: string | undefined): ThemeConfig => {
  return themes['dark-mode'];
};

// Default theme
export const DEFAULT_THEME: ThemeId = 'dark-mode';

// Legacy mapping for backward compatibility (URLs with old design1/2/3 and old theme names)
export const legacyThemeMapping: Record<string, ThemeId> = {
  'design1': 'dark-mode',
  'design2': 'dark-mode',
  'design3': 'dark-mode',
  'purple-dream': 'dark-mode',
  'pink-dream': 'dark-mode',
  'ocean-blue': 'dark-mode',
  'midnight-rose': 'dark-mode',
};

// Convert legacy theme ID to new ID
export const migrateLegacyTheme = (themeId: string | null): ThemeId => {
  return 'dark-mode';
};
