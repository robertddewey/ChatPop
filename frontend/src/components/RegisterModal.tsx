'use client';

import { useState, useEffect } from 'react';
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
    reserved_username: '',
  });
  const [usernameStatus, setUsernameStatus] = useState<{ checking: boolean; available: boolean | null; message: string }>({
    checking: false,
    available: null,
    message: '',
  });
  const [usernameValidation, setUsernameValidation] = useState<{ valid: boolean; message: string }>({
    valid: true,
    message: '',
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

  // Validate username format in real-time
  useEffect(() => {
    const username = formData.reserved_username;

    if (!username) {
      setUsernameValidation({ valid: true, message: '' });
      return;
    }

    // Check for non-alphanumeric characters (including spaces)
    const alphanumericRegex = /^[a-zA-Z0-9]+$/;
    if (!alphanumericRegex.test(username)) {
      setUsernameValidation({
        valid: false,
        message: 'Only letters and numbers allowed (no spaces or special characters)',
      });
      return;
    }

    setUsernameValidation({ valid: true, message: '' });
  }, [formData.reserved_username]);

  // Check username availability with debounce (only if format is valid)
  useEffect(() => {
    const username = formData.reserved_username.trim();

    if (!username || !usernameValidation.valid) {
      setUsernameStatus({ checking: false, available: null, message: '' });
      return;
    }

    setUsernameStatus({ checking: true, available: null, message: 'Checking...' });

    const timeoutId = setTimeout(async () => {
      try {
        const result = await authApi.checkUsername(username);
        setUsernameStatus({
          checking: false,
          available: result.available,
          message: result.message,
        });
      } catch (error) {
        setUsernameStatus({
          checking: false,
          available: null,
          message: 'Error checking username',
        });
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [formData.reserved_username, usernameValidation.valid]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    setLoading(true);

    try {
      await authApi.register(formData);
      await authApi.login(formData.email, formData.password);
      router.push(redirect);
    } catch (err: any) {
      const errorData = err.response?.data;

      if (typeof errorData === 'object' && errorData !== null) {
        const hasFieldErrors = Object.keys(errorData).some(key =>
          ['email', 'password', 'reserved_username'].includes(key)
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
        <h1 className={`text-2xl md:text-3xl font-bold ${styles.title} mb-4`}>
          {MARKETING.auth.register.title}
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
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${styles.input(!!fieldErrors.email)}`}
              placeholder=""
            />
            {fieldErrors.email && (
              <p className={`mt-1 text-sm ${styles.fieldError}`}>{fieldErrors.email}</p>
            )}
          </div>

          <div>
            <label htmlFor="reserved_username" className={`block text-sm font-bold ${styles.label} mb-2`}>
              Reserved Username (Optional)
            </label>
            <input
              type="text"
              id="reserved_username"
              value={formData.reserved_username}
              onChange={(e) => setFormData({ ...formData, reserved_username: e.target.value })}
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${styles.input(!!fieldErrors.reserved_username || !usernameValidation.valid || (usernameStatus.available === false))}`}
              placeholder=""
            />
            {fieldErrors.reserved_username && (
              <p className={`mt-1 text-sm ${styles.fieldError}`}>{fieldErrors.reserved_username}</p>
            )}
            {!fieldErrors.reserved_username && !usernameValidation.valid && (
              <p className={`mt-1 text-sm ${styles.fieldError}`}>{usernameValidation.message}</p>
            )}
            {!fieldErrors.reserved_username && usernameValidation.valid && usernameStatus.message && (
              <p className={`mt-1 text-sm ${usernameStatus.available === true ? 'text-green-600 dark:text-green-400' : usernameStatus.available === false ? styles.fieldError : styles.subtitle}`}>
                {usernameStatus.message}
              </p>
            )}
            {!fieldErrors.reserved_username && usernameValidation.valid && !usernameStatus.message && (
              <p className={`mt-1 text-xs ${styles.subtitle}`}>
                Letters and numbers only. Reserved for all chats.
              </p>
            )}
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
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:border-transparent ${styles.input(!!fieldErrors.password)}`}
              placeholder=""
            />
            {fieldErrors.password && (
              <p className={`mt-1 text-sm ${styles.fieldError}`}>{fieldErrors.password}</p>
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
