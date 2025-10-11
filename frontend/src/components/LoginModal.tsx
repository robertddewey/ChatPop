'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { authApi } from '@/lib/api';
import { MARKETING } from '@/lib/marketing';
import { X } from 'lucide-react';
import { isDarkTheme } from '@/lib/themes';

interface LoginModalProps {
  onClose: () => void;
  theme?: 'homepage' | 'chat';
  chatTheme?: 'dark-mode';
}

export default function LoginModal({ onClose, theme = 'homepage', chatTheme }: LoginModalProps) {
  // Force dark mode for homepage, use chat theme detection for chat pages
  const useDarkMode = theme === 'homepage' || (theme === 'chat' && chatTheme && isDarkTheme(chatTheme));
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get('redirect') || '/';

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });

  // Prevent body scrolling when modal is open (only on non-chat routes)
  // Chat routes already have body scroll locked via chat-layout.css
  useEffect(() => {
    const isChatRoute = window.location.pathname.startsWith('/chat/');
    if (!isChatRoute) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      if (!isChatRoute) {
        document.body.style.overflow = 'unset';
      }
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authApi.login(formData.email, formData.password);

      // On chat pages, auth-change listener will handle modal close and state refresh
      // On other pages, navigate to redirect
      const isChatRoute = window.location.pathname.startsWith('/chat/');
      if (!isChatRoute) {
        router.push(redirect);
      }
      // Modal will be closed by auth-change listener for chat routes
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid email or password');
      setLoading(false);
    }
  };

  const switchToRegister = () => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set('auth', 'register');
    const redirectParam = newParams.get('redirect');
    router.push(`${window.location.pathname}?${newParams.toString()}`);
  };

  // Theme-aware styles
  const styles = useDarkMode ? {
    // Dark mode styles (forced on homepage, conditional on chat pages)
    overlay: 'bg-black/75',
    container: 'bg-zinc-900 border border-zinc-800',
    title: 'text-zinc-100',
    subtitle: 'text-zinc-400',
    input: 'bg-zinc-800 border border-zinc-700 text-zinc-100 placeholder-zinc-500 focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400',
    label: 'text-zinc-300',
    button: 'bg-[#404eed] hover:bg-[#3640d9] text-white',
    link: 'text-cyan-400 hover:underline hover:text-cyan-300',
    error: 'bg-red-900/20 border-red-800 text-red-400',
    closeButton: 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800',
  } : {
    // Light mode styles (only used on non-homepage, non-dark-theme chat pages)
    overlay: 'bg-black/75',
    container: 'bg-white border-0',
    title: 'text-gray-900',
    subtitle: 'text-gray-600',
    input: 'bg-white border border-gray-300 text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
    label: 'text-gray-700',
    button: 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white',
    link: 'text-purple-600 hover:underline',
    error: 'bg-red-50 border-red-200 text-red-600',
    closeButton: 'text-gray-400 hover:text-gray-600 hover:bg-gray-100',
  };

  return (
    <div className={`fixed inset-0 z-[10000] flex items-center justify-center p-4 ${styles.overlay}`}>
      {/* Mobile: Full screen, Desktop: Max width */}
      <div className={`w-full max-w-md ${styles.container} rounded-2xl shadow-xl p-8 relative max-h-[90vh] overflow-y-auto`}>
        {/* Close Button */}
        <button
          onClick={onClose}
          className={`absolute top-4 right-4 p-2 rounded-lg transition-colors ${styles.closeButton}`}
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <h1 className={`text-2xl md:text-3xl font-bold ${styles.title} mb-4`}>
          {MARKETING.auth.login.title}
        </h1>

        {/* Error Message */}
        {error && (
          <div className={`mb-6 p-4 border rounded-lg ${styles.error}`}>
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className={`block text-sm font-bold ${styles.label} mb-2`}>
              {MARKETING.forms.email}
            </label>
            <input
              type="email"
              id="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className={`w-full px-4 py-3 rounded-xl ${styles.input} transition-colors focus:outline-none`}
              placeholder=""
            />
          </div>

          <div>
            <label htmlFor="password" className={`block text-sm font-bold ${styles.label} mb-2`}>
              {MARKETING.forms.password}
            </label>
            <input
              type="password"
              id="password"
              required
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className={`w-full px-4 py-3 rounded-xl ${styles.input} transition-colors focus:outline-none`}
              placeholder=""
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`w-full px-6 py-3 font-semibold rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed ${styles.button}`}
          >
            {loading ? MARKETING.auth.login.submitButtonLoading : MARKETING.auth.login.submitButton}
          </button>
        </form>

        {/* Switch to Register */}
        <p className={`mt-6 text-center ${styles.subtitle}`}>
          {MARKETING.auth.login.switchToRegister}{' '}
          <button
            onClick={switchToRegister}
            className={`font-medium ${styles.link}`}
          >
            {MARKETING.auth.login.switchToRegisterLink}
          </button>
        </p>
      </div>
    </div>
  );
}
