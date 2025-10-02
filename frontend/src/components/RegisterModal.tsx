'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { authApi } from '@/lib/api';
import { MARKETING } from '@/lib/marketing';
import { X } from 'lucide-react';

interface RegisterModalProps {
  onClose: () => void;
  theme?: 'homepage' | 'chat';
  chatTheme?: 'purple-dream' | 'ocean-blue' | 'dark-mode';
}

export default function RegisterModal({ onClose, theme = 'homepage', chatTheme }: RegisterModalProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get('redirect') || '/';

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    password_confirm: '',
    display_name: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    if (formData.password !== formData.password_confirm) {
      setFieldErrors({ password_confirm: 'Passwords do not match' });
      return;
    }

    setLoading(true);

    try {
      await authApi.register(formData);
      await authApi.login(formData.email, formData.password);
      router.push(redirect);
    } catch (err: any) {
      const errorData = err.response?.data;

      if (typeof errorData === 'object' && errorData !== null) {
        const hasFieldErrors = Object.keys(errorData).some(key =>
          ['email', 'password', 'password_confirm', 'display_name'].includes(key)
        );

        if (hasFieldErrors) {
          const errors: Record<string, string> = {};
          Object.entries(errorData).forEach(([field, msgs]: [string, any]) => {
            const errorList = Array.isArray(msgs) ? msgs : [msgs];
            errors[field] = errorList.join('. ');
          });
          setFieldErrors(errors);
        } else if (errorData.detail) {
          setError(errorData.detail);
        } else {
          setError('Failed to create account');
        }
      } else if (typeof errorData === 'string') {
        setError(errorData);
      } else {
        setError('Failed to create account');
      }

      setLoading(false);
    }
  };

  const switchToLogin = () => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set('auth', 'login');
    router.push(`${window.location.pathname}?${newParams.toString()}`);
  };

  // Theme-aware styles
  const isDarkChat = chatTheme === 'dark-mode';
  const isChat = theme === 'chat';

  const styles = {
    overlay: isChat
      ? isDarkChat
        ? 'bg-black/60 backdrop-blur-sm'
        : 'bg-black/20 backdrop-blur-sm'
      : 'bg-black/20 backdrop-blur-sm',
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
    input: (hasError: boolean) => isChat
      ? isDarkChat
        ? `bg-zinc-800 text-zinc-100 placeholder-zinc-500 focus:ring-cyan-400 ${hasError ? 'border-red-500' : 'border-zinc-700'}`
        : `bg-white text-gray-900 focus:ring-purple-500 ${hasError ? 'border-red-500' : 'border-gray-300'}`
      : `bg-white text-gray-900 focus:ring-purple-500 ${hasError ? 'border-red-500' : 'border-gray-300'}`,
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
    fieldError: isChat
      ? isDarkChat
        ? 'text-red-400'
        : 'text-red-600'
      : 'text-red-600',
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
          {MARKETING.auth.register.title}
        </h1>
        <p className={`${styles.subtitle} mb-8`}>
          {MARKETING.auth.register.subtitle}
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
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${styles.input(!!fieldErrors.email)}`}
              placeholder={MARKETING.placeholders.email}
            />
            {fieldErrors.email && (
              <p className={`mt-1 text-sm ${styles.fieldError}`}>{fieldErrors.email}</p>
            )}
          </div>

          <div>
            <label htmlFor="display_name" className={`block text-sm font-medium ${styles.label} mb-2`}>
              {MARKETING.forms.displayName}
            </label>
            <input
              type="text"
              id="display_name"
              value={formData.display_name}
              onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${styles.input(false)}`}
              placeholder={MARKETING.placeholders.displayName}
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
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${styles.input(!!fieldErrors.password)}`}
              placeholder={MARKETING.placeholders.password}
            />
            {fieldErrors.password && (
              <p className={`mt-1 text-sm ${styles.fieldError}`}>{fieldErrors.password}</p>
            )}
          </div>

          <div>
            <label htmlFor="password_confirm" className={`block text-sm font-medium ${styles.label} mb-2`}>
              {MARKETING.forms.passwordConfirm}
            </label>
            <input
              type="password"
              id="password_confirm"
              required
              value={formData.password_confirm}
              onChange={(e) => setFormData({ ...formData, password_confirm: e.target.value })}
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${styles.input(!!fieldErrors.password_confirm)}`}
              placeholder={MARKETING.placeholders.password}
            />
            {fieldErrors.password_confirm && (
              <p className={`mt-1 text-sm ${styles.fieldError}`}>{fieldErrors.password_confirm}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`w-full px-6 py-3 font-semibold rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed ${styles.button}`}
          >
            {loading ? MARKETING.auth.register.submitButtonLoading : MARKETING.auth.register.submitButton}
          </button>
        </form>

        {/* Switch to Login */}
        <p className={`mt-6 text-center ${styles.subtitle}`}>
          {MARKETING.auth.register.switchToLogin}{' '}
          <button
            onClick={switchToLogin}
            className={`font-medium ${styles.link}`}
          >
            {MARKETING.auth.register.switchToLoginLink}
          </button>
        </p>
      </div>
    </div>
  );
}
