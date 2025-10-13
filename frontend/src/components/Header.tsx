'use client';

import Link from 'next/link';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import { authApi } from '@/lib/api';

interface HeaderProps {
  backgroundClass?: string;
}

export default function Header({ backgroundClass }: HeaderProps = {}) {
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

  const headerClass = backgroundClass || "bg-white/90 dark:bg-gray-900/90";

  return (
    <header className={`sticky top-0 z-50 border-b border-white/10 ${headerClass} backdrop-blur-lg`}>
      <div className="container mx-auto px-4 py-4 flex justify-between items-center">
        <Link href="/" className="text-3xl font-black text-white tracking-tighter" style={{ fontWeight: 900, WebkitTextStroke: '0.5px white' }}>
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
              className="px-4 py-2 text-sm font-bold text-white hover:text-white/80 transition-all transform hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 cursor-pointer disabled:cursor-not-allowed"
            >
              {loading ? 'Logging out...' : 'Logout'}
            </button>
          ) : (
            <>
              <button
                onClick={() => router.push('/?auth=login', { scroll: false })}
                className="px-4 py-2 text-sm font-bold text-white hover:text-white/80 transition-all transform hover:scale-105 cursor-pointer"
              >
                Log in
              </button>
              <button
                onClick={() => router.push('/?auth=register', { scroll: false })}
                className="px-4 py-2 text-sm font-bold bg-white text-gray-900 rounded-lg hover:bg-white/90 transition-all transform hover:scale-105 shadow-sm cursor-pointer"
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
