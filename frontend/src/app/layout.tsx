import type { Metadata, Viewport } from "next";
import { Figtree } from "next/font/google";
import InAppBrowserGate from "@/components/InAppBrowserGate";
import "./globals.css";

const figtree = Figtree({
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ChatPop",
  description: "Real-time chat rooms",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "ChatPop",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
};

export function generateViewport() {
  return {
    width: 'device-width',
    initialScale: 1,
    themeColor: "#0a0a0a", // gray-900 to match gradient header
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" style={{ backgroundColor: '#0a0a0a' }}>
      <body
        style={{ backgroundColor: '#0a0a0a' }}
        className={`${figtree.className} antialiased`}
        suppressHydrationWarning
      >
        <InAppBrowserGate>
          {children}
        </InAppBrowserGate>
      </body>
    </html>
  );
}
