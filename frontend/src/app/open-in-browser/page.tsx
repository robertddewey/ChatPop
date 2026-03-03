'use client';

import {
  detectInAppBrowser,
  detectPlatform,
  detectSocialReferrer,
  browserLabels,
} from '@/lib/inAppBrowser';
import { useState, useEffect } from 'react';

export default function OpenInBrowserDemo() {
  const [userAgent, setUserAgent] = useState('');
  const [detected, setDetected] = useState<string | null>(null);
  const [platform, setPlatform] = useState<string>('unknown');
  const [referrer, setReferrer] = useState('');
  const [socialRef, setSocialRef] = useState<string | null>(null);
  // Note: detectSocialReferrer returns InAppBrowserType but we display it as string

  useEffect(() => {
    const ua = navigator.userAgent;
    setUserAgent(ua);
    const browser = detectInAppBrowser(ua);
    setDetected(browser ? browserLabels[browser] : null);
    setPlatform(detectPlatform(ua));
    setReferrer(document.referrer);
    setSocialRef(detectSocialReferrer(document.referrer));
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50 p-6 flex flex-col items-center justify-center">
      <h1 className="text-2xl font-bold mb-6">
        In-App Browser Detection Test
      </h1>

      <div className="w-full max-w-md space-y-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-sm text-zinc-400 mb-1">Detected in-app browser:</p>
          <p className="text-lg font-semibold">
            {detected ? (
              <span className="text-amber-400">{detected}</span>
            ) : (
              <span className="text-emerald-400">None (regular browser)</span>
            )}
          </p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-sm text-zinc-400 mb-1">Platform:</p>
          <p className="text-lg font-semibold">{platform}</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-sm text-zinc-400 mb-1">Referrer:</p>
          <p className="text-xs text-zinc-300 break-all font-mono">{referrer || '(empty)'}</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-sm text-zinc-400 mb-1">Social referrer detected:</p>
          <p className="text-lg font-semibold">
            {socialRef ? (
              <span className="text-amber-400">{socialRef}</span>
            ) : (
              <span className="text-emerald-400">None</span>
            )}
          </p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-sm text-zinc-400 mb-1">User Agent:</p>
          <p className="text-xs text-zinc-300 break-all font-mono">{userAgent}</p>
        </div>

        <p className="text-sm text-zinc-500 text-center pt-4">
          Share this page on Facebook/Instagram/X to test detection.
          <br />
          The gate wraps all pages, so any ChatPop link will trigger it.
        </p>
      </div>
    </div>
  );
}
