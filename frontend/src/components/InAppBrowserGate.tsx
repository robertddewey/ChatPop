'use client';

import { useState, useEffect, type ComponentType } from 'react';
import {
  detectInAppBrowser,
  detectPlatform,
  detectSocialReferrer,
  browserLabels,
  type InAppBrowserType,
  type PlatformType,
} from '@/lib/inAppBrowser';
import { FaFacebook, FaInstagram, FaTiktok, FaLinkedin, FaLine, FaSnapchat, FaXTwitter } from 'react-icons/fa6';
import { IoShareOutline } from 'react-icons/io5';
import { FiExternalLink } from 'react-icons/fi';

const browserIcons: Record<Exclude<InAppBrowserType, null>, { icon: ComponentType<{ className?: string }>; color: string }> = {
  facebook: { icon: FaFacebook, color: '#1877F2' },
  instagram: { icon: FaInstagram, color: '#E4405F' },
  tiktok: { icon: FaTiktok, color: '#ffffff' },
  linkedin: { icon: FaLinkedin, color: '#0A66C2' },
  line: { icon: FaLine, color: '#06C755' },
  snapchat: { icon: FaSnapchat, color: '#FFFC00' },
  twitter: { icon: FaXTwitter, color: '#ffffff' },
};

/** Strip tracking params (fbclid, etc.) from the current URL for a clean copy. */
function getCleanUrl(): string {
  if (typeof window === 'undefined') return '';
  const url = new URL(window.location.href);
  url.searchParams.delete('fbclid');
  url.searchParams.delete('utm_source');
  url.searchParams.delete('utm_medium');
  url.searchParams.delete('utm_campaign');
  url.searchParams.delete('utm_content');
  url.searchParams.delete('utm_term');
  return url.toString();
}

function InAppBrowserInterstitial({
  browser,
  platform,
}: {
  browser: Exclude<InAppBrowserType, null>;
  platform: PlatformType;
}) {
  const [copied, setCopied] = useState(false);
  const [arrowBottom, setArrowBottom] = useState(80);

  const isTwitterIos = browser === 'twitter' && platform === 'ios';

  // Track viewport height changes to keep the arrow aligned with Twitter's URL bar.
  // Twitter iOS shows a native slide-up panel that compresses our viewport;
  // when dismissed, the viewport expands and the URL bar drops to the true bottom.
  useEffect(() => {
    if (!isTwitterIos) return;

    const vv = window.visualViewport;
    const screenH = window.screen.height;

    function update() {
      const viewportH = vv ? vv.height : window.innerHeight;
      const chromeGap = screenH - viewportH;
      const panelOpen = chromeGap > 100;

      if (panelOpen) {
        setArrowBottom(10);
      } else {
        setArrowBottom(30);
      }
    }

    update();

    if (vv) {
      vv.addEventListener('resize', update);
      return () => vv.removeEventListener('resize', update);
    } else {
      window.addEventListener('resize', update);
      return () => window.removeEventListener('resize', update);
    }
  }, [isTwitterIos]);

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(getCleanUrl());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may be blocked in some in-app browsers
    }
  };

  const appName = browserLabels[browser];

  return (
    <div className="fixed inset-0 bg-zinc-950 flex flex-col items-center px-6 text-center z-[9999] overflow-hidden">
      {isTwitterIos ? (
        /* Animated arrow: enters from left, sweeps right and down to URL bar */
        <div className="absolute animate-gentle-bounce" style={{ bottom: `${arrowBottom}px`, left: '50%' }}>
          <svg width="120" height="100" viewBox="0 0 120 100" fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* Curved body — starts left, sweeps right then curves down to center */}
            <path d="M5 25C40 20 55 30 60 85" stroke="#ef4444" strokeWidth="3" strokeLinecap="round" fill="none" />
            {/* Arrowhead pointing down */}
            <path d="M52 78L60 95L68 78" stroke="#ef4444" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="#ef4444" />
          </svg>
        </div>
      ) : (
        /* Animated arrow pointing to ••• menu (top right) */
        <div className="absolute top-6 right-4 animate-bounce">
          <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* Curved arrow body — curves right then up */}
            <path d="M10 75C40 70 60 55 68 12" stroke="#ef4444" strokeWidth="3" strokeLinecap="round" fill="none" />
            {/* Arrowhead at the top of the curve */}
            <path d="M60 20L68 4L76 16" stroke="#ef4444" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="#ef4444" />
          </svg>
        </div>
      )}

      {/* Content - pushed down slightly to leave room for arrow */}
      <div className="flex flex-col items-center justify-center flex-1 max-w-sm w-full pb-8">
        {/* Logo */}
        <div className="mb-6">
          <h1 className="text-3xl font-black text-white tracking-tighter" style={{ fontWeight: 900, WebkitTextStroke: '0.5px white' }}>
            ChatPop
          </h1>
        </div>

        {/* Detected app badge */}
        {(() => {
          const { icon: Icon, color } = browserIcons[browser];
          return (
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-zinc-800 border border-zinc-700 mb-6">
              <Icon className="w-4 h-4" style={{ color }} />
              <span className="text-sm text-zinc-300">
                Opened from {appName}
              </span>
            </div>
          );
        })()}

        {/* Heading */}
        <h2 className="text-2xl font-bold text-zinc-50 mb-3">
          Open in your browser
        </h2>
        <p className="text-zinc-400 mb-8">
          ChatPop needs a full browser for real-time chat, voice messages, and media sharing.
        </p>

        {/* Instructions */}
        <div className="w-full space-y-4 mb-8">
          {isTwitterIos ? (
            <>
              <Step number={1} text={<>Tap the <Strong>URL bar</Strong> at the bottom</>} />
              <Step number={2} text={<>Select
                <span className="inline-flex items-center gap-1.5 align-middle ml-2 bg-white rounded-md -rotate-2 px-2 py-1">
                  <span className="text-zinc-900 font-medium text-xs">Open in browser</span>
                  <svg className="w-3.5 h-3.5 text-zinc-900 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                    <circle cx="12" cy="12" r="10" />
                    <path d="M2 12h20" />
                    <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
                  </svg>
                </span>
                <span className="text-zinc-500 text-[10px] ml-2">(or your browser&apos;s name)</span>
              </>} />
            </>
          ) : (
            <>
              <Step number={1} text={<>Tap the {platform === 'android' && browser !== 'snapchat' ? (
                <span className="inline-flex flex-col items-center gap-[3px] align-middle mx-1 px-1.5 py-1 bg-zinc-700 rounded">
                  <span className="w-[4px] h-[4px] rounded-full bg-zinc-50" />
                  <span className="w-[4px] h-[4px] rounded-full bg-zinc-50" />
                  <span className="w-[4px] h-[4px] rounded-full bg-zinc-50" />
                </span>
              ) : (
                <span className="inline-flex items-center gap-[3px] align-middle mx-1 px-1.5 py-1 bg-zinc-700 rounded">
                  <span className="w-[4px] h-[4px] rounded-full bg-zinc-50" />
                  <span className="w-[4px] h-[4px] rounded-full bg-zinc-50" />
                  <span className="w-[4px] h-[4px] rounded-full bg-zinc-50" />
                </span>
              )} menu (top right)</>} />
              {browser === 'facebook' ? (
                <Step number={2} text={<>Select
                  <span className="inline-flex items-center gap-1.5 align-middle ml-2 bg-white rounded-md -rotate-2 px-2 py-1">
                    <svg className="w-3.5 h-3.5 text-zinc-900 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                      <circle cx="12" cy="12" r="10" />
                      <path d="M2 12h20" />
                      <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
                    </svg>
                    <span className="text-zinc-900 font-medium text-xs">Open in browser</span>
                  </span>
                  <span className="text-zinc-500 text-[10px] ml-2">(or your browser&apos;s name)</span>
                </>} />
              ) : browser === 'linkedin' ? (
                <Step number={2} text={<>Select
                  <span className="inline-flex items-center gap-1.5 align-middle ml-2 bg-white rounded-md -rotate-2 px-2 py-1">
                    {platform === 'android' ? (
                      <FiExternalLink className="w-3.5 h-3.5 text-zinc-900 flex-shrink-0" />
                    ) : (
                      <IoShareOutline className="w-3.5 h-3.5 text-zinc-900 flex-shrink-0" />
                    )}
                    <span className="text-zinc-900 font-medium text-xs">Open in browser</span>
                  </span>
                  <span className="text-zinc-500 text-[10px] ml-2">(or your browser&apos;s name)</span>
                </>} />
              ) : browser === 'twitter' ? (
                <Step number={2} text={<>Select
                  <span className="inline-flex items-center gap-1.5 align-middle ml-2 bg-white rounded-md -rotate-2 px-2 py-1">
                    <FiExternalLink className="w-3.5 h-3.5 text-zinc-900 flex-shrink-0" />
                    <span className="text-zinc-900 font-medium text-xs">Open in browser</span>
                  </span>
                  <span className="text-zinc-500 text-[10px] ml-2">(or your browser&apos;s name)</span>
                </>} />
              ) : browser === 'snapchat' ? (
                <Step number={2} text={<>Select
                  <span className="inline-flex items-center align-middle ml-2 bg-white rounded-md -rotate-2 px-2 py-1">
                    <span className="text-zinc-900 font-medium text-xs">Open in browser</span>
                  </span>
                  <span className="text-zinc-500 text-[10px] ml-2">(or your browser&apos;s name)</span>
                </>} />
              ) : (
                <Step number={2} text={<>Select
                  <span className="inline-flex items-center align-middle ml-2 bg-white rounded-md -rotate-2 px-2 py-1">
                    <span className="text-zinc-900 font-medium text-xs">Open in browser</span>
                  </span>
                  <span className="text-zinc-500 text-[10px] ml-2">(or your browser&apos;s name)</span>
                </>} />
              )}
            </>
          )}
        </div>

        {/* Copy link button */}
        <button
          onClick={handleCopyLink}
          className="w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-indigo-500 hover:bg-indigo-600 active:bg-indigo-700 text-white font-semibold transition-colors"
        >
          {copied ? (
            <>
              <CheckIcon />
              Link copied!
            </>
          ) : (
            <>
              <CopyIcon />
              Copy link
            </>
          )}
        </button>
      </div>
    </div>
  );
}

function Step({ number, text }: { number: number; text: React.ReactNode }) {
  return (
    <div className="flex items-start gap-4 text-left">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center">
        <span className="text-sm font-bold text-indigo-400">{number}</span>
      </div>
      <p className="text-zinc-300 text-sm pt-1">{text}</p>
    </div>
  );
}

function Strong({ children }: { children: React.ReactNode }) {
  return <span className="font-semibold text-zinc-50">{children}</span>;
}

function CopyIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

export default function InAppBrowserGate({ children }: { children: React.ReactNode }) {
  const [inAppBrowser, setInAppBrowser] = useState<InAppBrowserType>(null);
  const [platform, setPlatform] = useState<PlatformType>('unknown');
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const ua = navigator.userAgent;
    const detectedBrowser = detectInAppBrowser(ua);
    const detectedPlatform = detectPlatform(ua);
    setPlatform(detectedPlatform);

    if (detectedBrowser) {
      setInAppBrowser(detectedBrowser);
    } else if (detectedPlatform === 'android') {
      // Fallback: check referrer for Chrome Custom Tab detection
      setInAppBrowser(detectSocialReferrer(document.referrer));
    }

    setChecked(true);
  }, []);

  // Before detection completes, render nothing (body bg is already dark)
  if (!checked) return null;

  if (inAppBrowser) {
    return <InAppBrowserInterstitial browser={inAppBrowser} platform={platform} />;
  }

  return <>{children}</>;
}
