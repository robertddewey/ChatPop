import type { Viewport } from "next";
import Script from "next/script";
import { Figtree } from "next/font/google";
import '../chat-layout.css';

const figtree = Figtree({
  subsets: ["latin"],
});

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover', // Required so position:fixed body with inset:0 extends into safe areas
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
            // Default to zinc-900 (#18181b) which is the Dark Mode theme background.
            // This ensures the html/body background matches the chat UI from the start,
            // preventing a black gap in iOS Safari's toolbar areas (which derive their
            // color from the page background).
            let bgColor = '#18181b';

            try {
              var storedTheme = localStorage.getItem('chat_theme_color');
              if (storedTheme) {
                var parsed = JSON.parse(storedTheme);
                var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                bgColor = prefersDark ? (parsed.dark || '#09090b') : (parsed.light || '#ffffff');
              }
            } catch (e) {
              bgColor = '#09090b';
            }

            // Inject style tag to set body and all page containers immediately
            // This targets body, Next.js root, and any divs with height/flex classes (the main container)
            const style = document.createElement('style');
            style.innerHTML = 'html, body { background-color: ' + bgColor + ' !important; }';
            document.head.appendChild(style);

          })();
        `}
      </Script>

      {/* iOS Safari: detect URL bar position and adjust header padding */}
      <Script id="ios-header-padding" strategy="afterInteractive">
        {`
          (function() {
            function updateHeaderPadding() {
              var header = document.querySelector('[data-chat-header]');
              if (!header) return;
              var chromeHeight = screen.height - window.innerHeight;
              // Small chrome = URL bar at bottom → add top padding for status bar clearance
              var topPad = chromeHeight < 120 ? '12px' : '0px';
              header.style.setProperty('padding-top', topPad, 'important');
            }

            // Run after DOM is ready and on resize
            if (document.readyState === 'loading') {
              document.addEventListener('DOMContentLoaded', updateHeaderPadding);
            } else {
              updateHeaderPadding();
            }
            window.addEventListener('resize', updateHeaderPadding);
            // Also observe for the header appearing (SPA navigation)
            var observer = new MutationObserver(function() {
              if (document.querySelector('[data-chat-header]')) updateHeaderPadding();
            });
            observer.observe(document.body, { childList: true, subtree: true });
          })();
        `}
      </Script>

      {/* theme-color meta tags removed — let browsers auto-detect from page content.
          Android Chrome samples the top background for the toolbar color.
          iOS Safari uses the page background for safe area tinting. */}
      <div className={figtree.className}>
        {children}
      </div>
    </>
  );
}
