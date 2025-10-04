'use client';

import Link from 'next/link';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import { authApi } from '@/lib/api';

export default function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isLoggedIn, setIsLoggedIn] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);

  // Check auth token on mount and when URL changes
  useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem('auth_token');
      console.log('[Header] Checking auth:', { hasToken: !!token });
      setIsLoggedIn(!!token);
    };

    checkAuth();

    // Listen for storage events (from other tabs/windows)
    window.addEventListener('storage', checkAuth);

    // Listen for custom auth events (from same window)
    window.addEventListener('auth-change', checkAuth);

    return () => {
      window.removeEventListener('storage', checkAuth);
      window.removeEventListener('auth-change', checkAuth);
    };
  }, [pathname, searchParams]);

  const handleLogout = async () => {
    setLoading(true);
    try {
      await authApi.logout();
      setIsLoggedIn(false);
      // Dispatch auth-change event for other components
      window.dispatchEvent(new Event('auth-change'));
      router.push('/');
    } catch (err) {
      console.error('Logout failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <header className="sticky top-0 z-50 border-b border-gray-200 dark:border-gray-700 bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm">
      <div className="container mx-auto px-4 py-4 flex justify-between items-center">
        <Link href="/" className="text-2xl font-black bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
          ChatPop
        </Link>
        <div className="flex gap-3">
          {isLoggedIn === null ? (
            // Loading state - show placeholder to prevent flash
            <div className="w-32 h-10" />
          ) : isLoggedIn ? (
            <button
              onClick={handleLogout}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 hover:text-purple-600 dark:hover:text-purple-400 transition-colors disabled:opacity-50"
            >
              {loading ? 'Logging out...' : 'Logout'}
            </button>
          ) : (
            <>
              <button
                onClick={() => router.push('/?auth=login')}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 hover:text-purple-600 dark:hover:text-purple-400 transition-colors"
              >
                Log in
              </button>
              <button
                onClick={() => router.push('/?auth=register')}
                className="px-4 py-2 text-sm font-medium bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
              >
                Sign Up
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
