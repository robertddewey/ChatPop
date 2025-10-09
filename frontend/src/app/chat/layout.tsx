import type { Viewport } from "next";
import Script from "next/script";
import '../chat-layout.css';

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover', // iOS Safari needs this for theme-color to work properly
};

// Note: Layout doesn't receive params in Next.js App Router
// Metadata generation must be in page.tsx, not layout.tsx
// We'll use client-side scripts to set theme-color dynamically instead

export default function ChatLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <>
      {/* Inject inline style in head to set body background BEFORE rendering */}
      <Script id="theme-bg-init" strategy="beforeInteractive">
        {`
          (function() {
            // Default to white for light mode, dark for dark mode
            let bgColor = '#ffffff';

            try {
              // Try to get theme from localStorage (set by page.tsx)
              const storedTheme = localStorage.getItem('chat_theme_color');
              if (storedTheme) {
                const parsed = JSON.parse(storedTheme);
                // Detect system color scheme preference
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                bgColor = prefersDark ? (parsed.dark || '#09090b') : (parsed.light || '#ffffff');
              }
            } catch (e) {
              // Fallback to white background
              bgColor = '#ffffff';
            }

            // Inject style tag to set body and all page containers immediately
            // This targets body, Next.js root, and any divs with height/flex classes (the main container)
            const style = document.createElement('style');
            style.innerHTML = 'html, body { background-color: ' + bgColor + ' !important; } #__next, #__next > div, [class*="h-\\\\[100dvh\\\\]"], [class*="flex-col"] { background: ' + bgColor + ' !important; background-image: none !important; }';
            document.head.appendChild(style);
          })();
        `}
      </Script>

      {/* Set theme-color meta tags after DOM is ready */}
      <Script id="theme-color-init" strategy="beforeInteractive">
        {`
          (function() {
            // Check if there's a stored theme in localStorage for this chat
            let themeColor = '#ffffff';  // Default to white (light theme)

            try {
              // Try to get theme from localStorage (set by page.tsx and ChatSettingsSheet)
              const storedTheme = localStorage.getItem('chat_theme_color');
              if (storedTheme) {
                const parsed = JSON.parse(storedTheme);
                // IMPORTANT: Use the 'light' property as the forced theme color
                // This overrides system preference - both light and dark meta tags get the same value
                // For light-mode theme: light = '#ffffff' (white)
                // For dark-mode theme: light = '#18181b' (zinc-900, but still called 'light')
                themeColor = parsed.light || themeColor;
              }
            } catch (e) {
              console.warn('Failed to parse stored theme color:', e);
            }

            // Force BOTH light and dark meta tags to the same color (override system preference)
            // This ensures the browser chrome matches our theme, not the OS setting

            // Update default meta tag
            let existingMeta = document.querySelector('meta[name="theme-color"]:not([media])');
            if (existingMeta) {
              existingMeta.setAttribute('content', themeColor);
            } else {
              const defaultMeta = document.createElement('meta');
              defaultMeta.name = 'theme-color';
              defaultMeta.content = themeColor;
              document.head.appendChild(defaultMeta);
            }

            // Update light mode meta tag (use theme color)
            let lightMeta = document.querySelector('meta[name="theme-color"][media="(prefers-color-scheme: light)"]');
            if (!lightMeta) {
              lightMeta = document.createElement('meta');
              lightMeta.setAttribute('name', 'theme-color');
              lightMeta.setAttribute('media', '(prefers-color-scheme: light)');
              document.head.appendChild(lightMeta);
            }
            lightMeta.setAttribute('content', themeColor);

            // Update dark mode meta tag (ALSO use theme color - same as light)
            let darkMeta = document.querySelector('meta[name="theme-color"][media="(prefers-color-scheme: dark)"]');
            if (!darkMeta) {
              darkMeta = document.createElement('meta');
              darkMeta.setAttribute('name', 'theme-color');
              darkMeta.setAttribute('media', '(prefers-color-scheme: dark)');
              document.head.appendChild(darkMeta);
            }
            darkMeta.setAttribute('content', themeColor);
          })();
        `}
      </Script>
      {children}
    </>
  );
}
