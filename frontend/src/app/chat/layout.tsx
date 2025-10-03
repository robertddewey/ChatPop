import type { Viewport } from "next";
import Script from "next/script";
import "../chat-layout.css";

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover', // iOS Safari needs this for theme-color to work properly
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
            // Theme color mapping
            const themeColors = {
              'purple-dream': { light: '#ffffff', dark: '#1f2937' },
              'ocean-blue': { light: '#ffffff', dark: '#1f2937' },
              'dark-mode': { light: '#18181b', dark: '#18181b' }
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

              return 'purple-dream'; // default
            }

            const theme = getTheme();
            const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const color = isDark ? themeColors[theme].dark : themeColors[theme].light;

            // Set theme-color meta tags with media queries
            const lightMeta = document.createElement('meta');
            lightMeta.name = 'theme-color';
            lightMeta.media = '(prefers-color-scheme: light)';
            lightMeta.content = themeColors[theme].light;
            document.head.appendChild(lightMeta);

            const darkMeta = document.createElement('meta');
            darkMeta.name = 'theme-color';
            darkMeta.media = '(prefers-color-scheme: dark)';
            darkMeta.content = themeColors[theme].dark;
            document.head.appendChild(darkMeta);

            // Set body background (suppressHydrationWarning in root layout handles the warning)
            document.body.style.backgroundColor = color;
          })();
        `}
      </Script>
      {children}
    </>
  );
}
