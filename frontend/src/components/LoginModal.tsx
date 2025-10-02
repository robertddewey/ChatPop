'use client';

import { useState } from 'react';
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authApi.login(formData.email, formData.password);
      router.push(redirect);
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
  const isDarkChat = chatTheme === 'dark-mode';
  const isChat = theme === 'chat';

  const styles = {
    overlay: 'bg-black/20 backdrop-blur-sm',
    container: isChat
      ? isDarkChat
        ? 'bg-zinc-900 border border-zinc-800'
        : 'bg-white border border-gray-200'
      : 'bg-white',
    title: isChat
      ? isDarkChat
        ? 'text-zinc-100'
        : 'text-gray-900'
      : 'text-gray-900',
    subtitle: isChat
      ? isDarkChat
        ? 'text-zinc-400'
        : 'text-gray-600'
      : 'text-gray-600',
    input: isChat
      ? isDarkChat
        ? 'bg-zinc-800 border-zinc-700 text-zinc-100 placeholder-zinc-500 focus:ring-cyan-400'
        : 'bg-white border-gray-300 text-gray-900 focus:ring-purple-500'
      : 'bg-white border-gray-300 text-gray-900 focus:ring-purple-500',
    label: isChat
      ? isDarkChat
        ? 'text-zinc-300'
        : 'text-gray-700'
      : 'text-gray-700',
    button: isChat
      ? isDarkChat
        ? 'bg-cyan-400 hover:bg-cyan-500 text-cyan-950'
        : 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white'
      : 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white',
    link: isChat
      ? isDarkChat
        ? 'text-cyan-400 hover:text-cyan-300'
        : 'text-purple-600 hover:underline'
      : 'text-purple-600 hover:underline',
    error: isChat
      ? isDarkChat
        ? 'bg-red-900/20 border-red-800 text-red-400'
        : 'bg-red-50 border-red-200 text-red-600'
      : 'bg-red-50 border-red-200 text-red-600',
    closeButton: isChat
      ? isDarkChat
        ? 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
        : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
      : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100',
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
        <h1 className={`text-3xl font-bold ${styles.title} mb-2`}>
          {MARKETING.auth.login.title}
        </h1>
        <p className={`${styles.subtitle} mb-8`}>
          {MARKETING.auth.login.subtitle}
        </p>

        {/* Error Message */}
        {error && (
          <div className={`mb-6 p-4 border rounded-lg ${styles.error}`}>
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="email" className={`block text-sm font-medium ${styles.label} mb-2`}>
              {MARKETING.forms.email}
            </label>
            <input
              type="email"
              id="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${styles.input}`}
              placeholder={MARKETING.placeholders.email}
            />
          </div>

          <div>
            <label htmlFor="password" className={`block text-sm font-medium ${styles.label} mb-2`}>
              {MARKETING.forms.password}
            </label>
            <input
              type="password"
              id="password"
              required
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${styles.input}`}
              placeholder={MARKETING.placeholders.password}
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
