export type InAppBrowserType =
  | 'facebook'
  | 'instagram'
  | 'tiktok'
  | 'linkedin'
  | 'line'
  | 'snapchat'
  | 'twitter'
  | null;

export type PlatformType = 'ios' | 'android' | 'unknown';

/**
 * Detect if the current browser is an in-app WebView from a social media app.
 */
export function detectInAppBrowser(userAgent: string): InAppBrowserType {
  if (/FBAN|FBAV/i.test(userAgent)) return 'facebook';
  if (/Instagram/i.test(userAgent)) return 'instagram';
  if (/TikTok|Musical\.ly/i.test(userAgent)) return 'tiktok';
  if (/LinkedInApp/i.test(userAgent)) return 'linkedin';
  if (/\bLine\//i.test(userAgent)) return 'line';
  if (/Snapchat/i.test(userAgent)) return 'snapchat';
  if (/Twitter/i.test(userAgent)) return 'twitter';
  return null;
}

/**
 * Detect the user's platform (iOS vs Android).
 */
export function detectPlatform(userAgent: string): PlatformType {
  if (/iPhone|iPad|iPod/i.test(userAgent)) return 'ios';
  if (/Android/i.test(userAgent)) return 'android';
  return 'unknown';
}

/**
 * Check if the document referrer suggests the user came from a social app.
 * Used on Android where Chrome Custom Tabs are undetectable via UA.
 */
export function detectSocialReferrer(referrer: string): InAppBrowserType {
  const r = referrer.toLowerCase();
  if (r.includes('t.co') || r.includes('twitter.com') || r.includes('x.com') || r.includes('com.twitter.android')) return 'twitter';
  if (r.includes('lnkd.in') || r.includes('linkedin.com') || r.includes('com.linkedin.android')) return 'linkedin';
  if (r.includes('facebook.com') || r.includes('fb.com') || r.includes('com.facebook.katana')) return 'facebook';
  if (r.includes('instagram.com') || r.includes('com.instagram.android')) return 'instagram';
  if (r.includes('com.zhiliaoapp.musically') || r.includes('tiktok.com')) return 'tiktok';
  if (r.includes('com.snapchat.android') || r.includes('snapchat.com')) return 'snapchat';
  if (r.includes('jp.naver.line.android') || r.includes('line.me')) return 'line';
  return null;
}

/** Human-readable label for each in-app browser. */
export const browserLabels: Record<Exclude<InAppBrowserType, null>, string> = {
  facebook: 'Facebook',
  instagram: 'Instagram',
  tiktok: 'TikTok',
  linkedin: 'LinkedIn',
  line: 'LINE',
  snapchat: 'Snapchat',
  twitter: 'X (Twitter)',
};
