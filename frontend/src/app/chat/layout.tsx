import type { Viewport, Metadata } from "next";
import Script from "next/script";
import "../chat-layout.css";

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover', // iOS Safari needs this for theme-color to work properly
};

// Server-side metadata with default theme colors
// Note: This will be overridden client-side based on actual theme
export const metadata: Metadata = {
  other: {
    'theme-color': '#ffffff',
  },
};

export default function ChatLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <>
      {/* Set theme-color and body background BEFORE React hydration */}
      <Script id="theme-color-init" strategy="beforeInteractive">
        {`
          (function() {
            // Theme color mapping (for browser URL bar)
            const themeColors = {
              'pink-dream': { light: '#fce7f3', dark: '#1e1b4b' },
              'ocean-blue': { light: '#ffffff', dark: '#1f2937' },
              'dark-mode': { light: '#18181b', dark: '#18181b' }
            };

            // Body background colors (match container backgrounds)
            const backgroundColors = {
              'pink-dream': { light: '#fdf2f8', dark: '#1e1b4b' }, // pink-50 / indigo-950
              'ocean-blue': { light: '#f0f9ff', dark: '#111827' },   // sky-50 / gray-900
              'dark-mode': { light: '#09090b', dark: '#09090b' }     // zinc-950 / zinc-950
            };

            // Get theme from URL or localStorage
            function getTheme() {
              const params = new URLSearchParams(window.location.search);
              const urlTheme = params.get('design');
              if (urlTheme && themeColors[urlTheme]) return urlTheme;

              // Extract chat code from URL path
              const match = window.location.pathname.match(/\\/chat\\/([^\\/]+)/);
              if (match) {
                const code = match[1];
                const stored = localStorage.getItem('chatpop_theme_' + code);
                if (stored && themeColors[stored]) return stored;
              }

              return 'pink-dream'; // default
            }

            const theme = getTheme();
            const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const themeColor = isDark ? themeColors[theme].dark : themeColors[theme].light;
            const bgColor = isDark ? backgroundColors[theme].dark : backgroundColors[theme].light;

            // Update or create theme-color meta tags
            // Chrome on iOS needs existing meta tag to be updated, not dynamically created

            // Find existing theme-color meta tag (from server-side metadata)
            let existingMeta = document.querySelector('meta[name="theme-color"]:not([media])');
            if (existingMeta) {
              existingMeta.setAttribute('content', themeColor);
            } else {
              // Fallback: create if doesn't exist
              const defaultMeta = document.createElement('meta');
              defaultMeta.name = 'theme-color';
              defaultMeta.content = themeColor;
              document.head.appendChild(defaultMeta);
            }

            // Add media-query specific meta tags for Safari
            let lightMeta = document.querySelector('meta[name="theme-color"][media="(prefers-color-scheme: light)"]');
            if (!lightMeta) {
              lightMeta = document.createElement('meta');
              lightMeta.setAttribute('name', 'theme-color');
              lightMeta.setAttribute('media', '(prefers-color-scheme: light)');
              document.head.appendChild(lightMeta);
            }
            lightMeta.setAttribute('content', themeColors[theme].light);

            let darkMeta = document.querySelector('meta[name="theme-color"][media="(prefers-color-scheme: dark)"]');
            if (!darkMeta) {
              darkMeta = document.createElement('meta');
              darkMeta.setAttribute('name', 'theme-color');
              darkMeta.setAttribute('media', '(prefers-color-scheme: dark)');
              document.head.appendChild(darkMeta);
            }
            darkMeta.setAttribute('content', themeColors[theme].dark);

            // Set body background to match theme (suppressHydrationWarning in root layout handles the warning)
            document.body.style.backgroundColor = bgColor;
          })();
        `}
      </Script>
      {children}
    </>
  );
}
