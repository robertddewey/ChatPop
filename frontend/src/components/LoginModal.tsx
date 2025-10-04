'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { authApi } from '@/lib/api';
import { MARKETING } from '@/lib/marketing';
import { X } from 'lucide-react';

interface LoginModalProps {
  onClose: () => void;
  theme?: 'homepage' | 'chat';
  chatTheme?: 'purple-dream' | 'ocean-blue' | 'dark-mode';
}

export default function LoginModal({ onClose, theme = 'homepage', chatTheme }: LoginModalProps) {
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

  // Theme-aware styles - now uses Tailwind dark: variants to respond to OS preference
  const styles = {
    overlay: 'bg-black/75',
    container: 'bg-white dark:bg-zinc-900 border-0 dark:border dark:border-zinc-800',
    title: 'text-gray-900 dark:text-zinc-100',
    subtitle: 'text-gray-600 dark:text-zinc-400',
    input: 'bg-white dark:bg-zinc-800 border border-gray-300 dark:border-zinc-700 text-gray-900 dark:text-zinc-100 placeholder-gray-400 dark:placeholder-zinc-500 focus:ring-2 focus:ring-purple-500 dark:focus:ring-cyan-400 focus:border-purple-500 dark:focus:border-cyan-400',
    label: 'text-gray-700 dark:text-zinc-300',
    button: 'bg-gradient-to-r from-purple-600 to-blue-600 dark:bg-cyan-400 hover:from-purple-700 hover:to-blue-700 dark:hover:bg-cyan-500 text-white dark:text-cyan-950',
    link: 'text-purple-600 dark:text-cyan-400 hover:underline dark:hover:text-cyan-300',
    error: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-600 dark:text-red-400',
    closeButton: 'text-gray-400 dark:text-zinc-400 hover:text-gray-600 dark:hover:text-zinc-200 hover:bg-gray-100 dark:hover:bg-zinc-800',
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
