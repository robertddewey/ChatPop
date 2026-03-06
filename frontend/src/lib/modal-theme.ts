export const modalTheme = {
  // Backdrop
  backdrop: {
    dark: 'bg-black/60 backdrop-blur-md',
    light: 'bg-black/60 backdrop-blur-md',
  },
  // Container
  container: {
    dark: 'bg-zinc-900',
    light: 'bg-white',
  },
  border: {
    dark: 'border border-zinc-700',
    light: 'border border-gray-200',
  },
  rounded: 'rounded-2xl',
  shadow: 'shadow-xl',
  // Title text
  title: {
    dark: 'text-zinc-50',
    light: 'text-gray-900',
  },
  // Body/description text
  body: {
    dark: 'text-zinc-400',
    light: 'text-gray-600',
  },
  // Primary action button (Join, Sign In, Confirm, Thank)
  primaryButton: {
    dark: 'bg-[#404eed] hover:bg-[#3640d9] text-white',
    light: 'bg-[#404eed] hover:bg-[#3640d9] text-white',
  },
  // Secondary/dismiss button (Got It, Cancel, Back)
  secondaryButton: {
    dark: 'bg-zinc-700 hover:bg-zinc-600 text-zinc-50',
    light: 'bg-gray-100 hover:bg-gray-200 text-gray-900',
  },
  // Input fields
  input: {
    dark: 'bg-zinc-800 border border-zinc-600 text-zinc-50 placeholder-zinc-400 focus:ring-2 focus:ring-cyan-400',
    light: 'bg-white border border-gray-300 text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-purple-500',
  },
  // Close/X button
  closeButton: {
    dark: 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800',
    light: 'text-gray-400 hover:text-gray-600 hover:bg-gray-100',
  },
  // Error messages
  error: {
    dark: 'bg-red-900/20 border border-red-800 text-red-400',
    light: 'bg-red-50 border border-red-200 text-red-600',
  },
};

// Helper: get styles for current theme
export const getModalTheme = (isDark: boolean) => ({
  backdrop: isDark ? modalTheme.backdrop.dark : modalTheme.backdrop.light,
  container: isDark ? modalTheme.container.dark : modalTheme.container.light,
  border: isDark ? modalTheme.border.dark : modalTheme.border.light,
  rounded: modalTheme.rounded,
  shadow: modalTheme.shadow,
  title: isDark ? modalTheme.title.dark : modalTheme.title.light,
  body: isDark ? modalTheme.body.dark : modalTheme.body.light,
  primaryButton: isDark ? modalTheme.primaryButton.dark : modalTheme.primaryButton.light,
  secondaryButton: isDark ? modalTheme.secondaryButton.dark : modalTheme.secondaryButton.light,
  input: isDark ? modalTheme.input.dark : modalTheme.input.light,
  closeButton: isDark ? modalTheme.closeButton.dark : modalTheme.closeButton.light,
  error: isDark ? modalTheme.error.dark : modalTheme.error.light,
});
