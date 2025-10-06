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
            // Only dark-mode theme available - use zinc-900 background
            const bgColor = '#09090b';

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
            // Only dark-mode theme - always use zinc-900 color
            const themeColor = '#18181b';

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

            // Add media-query specific meta tags for Safari (same color for both modes)
            let lightMeta = document.querySelector('meta[name="theme-color"][media="(prefers-color-scheme: light)"]');
            if (!lightMeta) {
              lightMeta = document.createElement('meta');
              lightMeta.setAttribute('name', 'theme-color');
              lightMeta.setAttribute('media', '(prefers-color-scheme: light)');
              document.head.appendChild(lightMeta);
            }
            lightMeta.setAttribute('content', themeColor);

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
