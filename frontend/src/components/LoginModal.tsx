'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { authApi } from '@/lib/api';
import { MARKETING } from '@/lib/marketing';
import { X } from 'lucide-react';
import { getModalTheme } from '@/lib/modal-theme';

interface LoginFormContentProps {
  onClose: () => void;
  onSwitchToRegister?: () => void;
  hideTitle?: boolean;
}

export function LoginFormContent({ onClose, onSwitchToRegister, hideTitle }: LoginFormContentProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get('redirect') || '/';

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });

  const useDarkMode = true;
  const mt = getModalTheme(useDarkMode);
  const styles = {
    title: mt.title,
    subtitle: 'text-zinc-300',
    input: mt.input,
    label: 'text-zinc-200',
    link: 'text-cyan-400 hover:underline hover:text-cyan-300',
    error: mt.error,
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authApi.login(formData.email, formData.password);

      const isChatRoute = window.location.pathname.startsWith('/chat/');
      if (!isChatRoute) {
        router.push(redirect);
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Invalid email or password');
      setLoading(false);
    }
  };

  const switchToRegister = () => {
    if (onSwitchToRegister) {
      onSwitchToRegister();
      return;
    }
    const path = window.location.pathname;
    // Chat page path-based auth: replace /login with /signup
    if (path.endsWith('/login')) {
      router.replace(path.replace(/\/login$/, '/signup'));
    } else {
      const newParams = new URLSearchParams(searchParams);
      newParams.set('auth', 'register');
      router.replace(`${path}?${newParams.toString()}`);
    }
  };

  return (
    <>
      {!hideTitle && (
        <h1 className={`text-2xl md:text-3xl font-bold ${styles.title} mb-4`}>
          {MARKETING.auth.login.title}
        </h1>
      )}

      {error && (
        <div className={`mb-6 p-4 border rounded-lg ${styles.error}`}>
          {error}
        </div>
      )}

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
          className={`w-full px-6 py-3 font-semibold rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${mt.primaryButton}`}
        >
          {loading ? MARKETING.auth.login.submitButtonLoading : MARKETING.auth.login.submitButton}
        </button>
      </form>

      <p className={`mt-6 text-center ${styles.subtitle}`}>
        {MARKETING.auth.login.switchToRegister}{' '}
        <button
          onClick={switchToRegister}
          className={`font-medium cursor-pointer ${styles.link}`}
        >
          {MARKETING.auth.login.switchToRegisterLink}
        </button>
      </p>
    </>
  );
}

interface LoginModalProps {
  onClose: () => void;
  theme?: 'homepage' | 'chat';
  chatTheme?: 'dark-mode';
}

export default function LoginModal({ onClose }: LoginModalProps) {
  const useDarkMode = true;
  const mt = getModalTheme(useDarkMode);
  const styles = {
    overlay: mt.backdrop,
    container: `${mt.container} ${mt.border}`,
    closeButton: mt.closeButton,
  };

  // Prevent body scrolling when modal is open on desktop (only on non-chat routes)
  useEffect(() => {
    const isChatRoute = window.location.pathname.startsWith('/chat/');
    if (!isChatRoute) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      if (!isChatRoute) {
        document.body.style.overflow = '';
      }
    };
  }, []);

  return (
    <div className={`fixed inset-0 z-[10000] flex items-center justify-center p-4 ${styles.overlay}`}>
      <div className={`w-full max-w-md ${styles.container} ${mt.rounded} ${mt.shadow} p-8 relative max-h-[90vh] overflow-y-auto`}>
        <button
          onClick={onClose}
          className={`absolute top-4 right-4 p-2 rounded-lg transition-colors cursor-pointer ${styles.closeButton}`}
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        <LoginFormContent onClose={onClose} />
      </div>
    </div>
  );
}
