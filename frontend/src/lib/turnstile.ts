/**
 * Cloudflare Turnstile session-based bot detection.
 * Verifies the user is human once per session via /api/auth/verify-human/.
 * Most users see nothing (invisible check). Suspicious traffic gets a brief challenge.
 */

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: string | HTMLElement,
        options: {
          sitekey: string;
          action?: string;
          appearance?: 'always' | 'execute' | 'interaction-only';
          callback: (token: string) => void;
          'error-callback'?: (error?: unknown) => void;
          'expired-callback'?: () => void;
          size?: 'normal' | 'compact' | 'flexible';
          theme?: 'light' | 'dark' | 'auto';
        }
      ) => string;
      remove: (widgetId: string) => void;
    };
  }
}

let scriptPromise: Promise<void> | null = null;
let verified = false;
let verifyPromise: Promise<boolean> | null = null;

/**
 * Reset the in-memory verification cache. Call this on logout — Django's
 * logout() flushes the server session (wiping turnstile_verified), so the
 * frontend must re-verify on the next protected request.
 */
export function resetTurnstileVerification(): void {
  verified = false;
  verifyPromise = null;
}

function loadTurnstileScript(): Promise<void> {
  if (scriptPromise) return scriptPromise;
  if (typeof window === 'undefined') return Promise.resolve();
  if (window.turnstile) return Promise.resolve();

  scriptPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      scriptPromise = null;
      reject(new Error('Failed to load Turnstile script'));
    };
    document.head.appendChild(script);
  });

  return scriptPromise;
}

function ensureContainer(): HTMLElement {
  const containerId = 'turnstile-container';
  let container = document.getElementById(containerId);
  if (container) return container;

  const overlay = document.createElement('div');
  overlay.id = 'turnstile-overlay';
  overlay.style.cssText = `
    position: fixed;
    inset: 0;
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
  `;

  container = document.createElement('div');
  container.id = containerId;
  container.style.cssText = `
    border-radius: 16px;
    padding: 24px;
    background: #18181b;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  `;

  overlay.appendChild(container);
  document.body.appendChild(overlay);
  return container;
}

function cleanup(widgetId: string | null) {
  if (widgetId && window.turnstile) {
    try { window.turnstile.remove(widgetId); } catch { /* already removed */ }
  }
  const overlay = document.getElementById('turnstile-overlay');
  if (overlay) overlay.remove();
}

function getTurnstileTokenFromWidget(): Promise<string | null> {
  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  if (!siteKey || !window.turnstile) return Promise.resolve(null);

  const container = ensureContainer();
  let widgetId: string | null = null;

  return new Promise<string | null>((resolve) => {
    try {
      widgetId = window.turnstile!.render(container, {
        sitekey: siteKey,
        action: 'verify-session',
        appearance: 'interaction-only',
        size: 'normal',
        theme: 'dark',
        callback: (token: string) => {
          cleanup(widgetId);
          resolve(token);
        },
        'error-callback': () => {
          cleanup(widgetId);
          resolve(null);
        },
        'expired-callback': () => {
          cleanup(widgetId);
          resolve(null);
        },
      });
    } catch {
      cleanup(widgetId);
      resolve(null);
    }
  });
}

// Helper to get CSRF token from cookies (standalone, avoids importing from api.ts)
function getCsrfToken(): string | null {
  const name = 'csrftoken';
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
}

/**
 * Verify the current user is human. Called once per session.
 * Returns true if verified (or if Turnstile is not configured).
 * Subsequent calls return immediately without showing the widget.
 */
export async function verifyHuman(): Promise<boolean> {
  // Already verified this page session
  if (verified) return true;

  // Check sessionStorage (survives page navigations within same tab)
  if (typeof window !== 'undefined' && sessionStorage.getItem('turnstile_verified')) {
    verified = true;
    return true;
  }

  // No site key = development mode, always pass
  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  if (!siteKey) {
    verified = true;
    return true;
  }

  // If a verification is already in progress, wait for it
  if (verifyPromise) return verifyPromise;

  verifyPromise = (async () => {
    try {
      // First, check if the server session is already verified (no token needed)
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      const csrfToken = getCsrfToken();
      if (csrfToken) headers['X-CSRFToken'] = csrfToken;

      const checkResponse = await fetch('/api/auth/verify-human/', {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({}),
      });

      if (checkResponse.ok) {
        const data = await checkResponse.json();
        if (data.already_verified || data.verified) {
          verified = true;
          sessionStorage.setItem('turnstile_verified', '1');
          return true;
        }
      }
      // If 400 (token required), proceed to get a token
    } catch {
      // Network error checking session — proceed with widget
    }

    // Load Turnstile script and get a token from the widget
    try {
      await loadTurnstileScript();
    } catch {
      verified = true; // Fail open
      return true;
    }

    const token = await getTurnstileTokenFromWidget();
    if (!token) {
      // Widget failed — fail open to not block users
      verified = true;
      return true;
    }

    // Send token to backend for verification
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      const csrfToken = getCsrfToken();
      if (csrfToken) headers['X-CSRFToken'] = csrfToken;

      const response = await fetch('/api/auth/verify-human/', {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({ turnstile_token: token }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.verified) {
          verified = true;
          sessionStorage.setItem('turnstile_verified', '1');
          return true;
        }
      }
    } catch {
      // Backend rejected — fail open
      verified = true;
      return true;
    }

    return false;
  })();

  const result = await verifyPromise;
  verifyPromise = null;
  return result;
}
