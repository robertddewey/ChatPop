import type { Viewport, Metadata } from "next";
import Script from "next/script";
import '../chat-layout.css';

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
      {/* Inject inline style in head to set body background BEFORE rendering */}
      <Script id="theme-bg-init" strategy="beforeInteractive">
        {`
          (function() {
            // Body background colors (match container backgrounds)
            const backgroundColors = {
              'pink-dream': { light: '#fdf2f8', dark: '#1e1b4b' },
              'ocean-blue': { light: '#f0f9ff', dark: '#111827' },
              'dark-mode': { light: '#09090b', dark: '#09090b' }
            };

            // Get theme from URL or localStorage
            function getTheme() {
              const params = new URLSearchParams(window.location.search);
              const urlTheme = params.get('design');
              if (urlTheme && backgroundColors[urlTheme]) return urlTheme;

              const match = window.location.pathname.match(/\\/chat\\/([^\\/]+)/);
              if (match) {
                const code = match[1];
                const stored = localStorage.getItem('chatpop_theme_' + code);
                if (stored && backgroundColors[stored]) return stored;
              }

              return 'pink-dream';
            }

            const theme = getTheme();
            const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const bgColor = isDark ? backgroundColors[theme].dark : backgroundColors[theme].light;

            // Inject style tag to set body background immediately
            const style = document.createElement('style');
            style.innerHTML = 'body { background-color: ' + bgColor + ' !important; }';
            document.head.appendChild(style);
          })();
        `}
      </Script>

      {/* Set theme-color meta tags after DOM is ready */}
      <Script id="theme-color-init" strategy="beforeInteractive">
        {`
          (function() {
            // Theme color mapping (for browser URL bar)
            const themeColors = {
              'pink-dream': { light: '#fce7f3', dark: '#1e1b4b' },
              'ocean-blue': { light: '#ffffff', dark: '#1f2937' },
              'dark-mode': { light: '#18181b', dark: '#18181b' }
            };

            // Get theme from URL or localStorage
            function getTheme() {
              const params = new URLSearchParams(window.location.search);
              const urlTheme = params.get('design');
              if (urlTheme && themeColors[urlTheme]) return urlTheme;

              const match = window.location.pathname.match(/\\/chat\\/([^\\/]+)/);
              if (match) {
                const code = match[1];
                const stored = localStorage.getItem('chatpop_theme_' + code);
                if (stored && themeColors[stored]) return stored;
              }

              return 'pink-dream';
            }

            const theme = getTheme();
            const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const themeColor = isDark ? themeColors[theme].dark : themeColors[theme].light;

            // Find existing theme-color meta tag (from server-side metadata)
            let existingMeta = document.querySelector('meta[name="theme-color"]:not([media])');
            if (existingMeta) {
              existingMeta.setAttribute('content', themeColor);
            } else {
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
          })();
        `}
      </Script>
      {children}
    </>
  );
}
