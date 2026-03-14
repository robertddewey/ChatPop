'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { authApi, chatApi } from '@/lib/api';
import { validateUsername } from '@/lib/validation';
import { MARKETING } from '@/lib/marketing';
import { getFingerprint } from '@/lib/usernameStorage';
import { X, Dices, ChevronLeft, ChevronRight } from 'lucide-react';
import { getModalTheme } from '@/lib/modal-theme';

interface RegisterFormContentProps {
  onClose: () => void;
  onSwitchToLogin?: () => void;
  hideTitle?: boolean;
}

export function RegisterFormContent({ onClose, onSwitchToLogin, hideTitle }: RegisterFormContentProps) {
  const useDarkMode = true;
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
  const [isSuggestingUsername, setIsSuggestingUsername] = useState(false);
  const [usernameSource, setUsernameSource] = useState<'manual' | 'dice'>('manual');
  const [diceUsername, setDiceUsername] = useState<string | null>(null);
  const [isRotating, setIsRotating] = useState(false);

  // Avatar state
  const [avatarSeeds, setAvatarSeeds] = useState<string[]>(() => [crypto.randomUUID()]);
  const [avatarIndex, setAvatarIndex] = useState(0);

  // Fingerprint state
  const [fingerprint, setFingerprint] = useState<string | null>(null);

  const getAvatarUrl = (seed: string, size: number = 80): string => {
    return `https://api.dicebear.com/7.x/pixel-art/svg?seed=${encodeURIComponent(seed)}&size=${size}`;
  };

  const currentAvatarSeed = avatarSeeds[avatarIndex];
  const currentAvatarUrl = getAvatarUrl(currentAvatarSeed);

  const handleAvatarPrev = () => {
    if (avatarIndex > 0) setAvatarIndex(avatarIndex - 1);
  };
  const handleAvatarNext = () => {
    if (avatarIndex < avatarSeeds.length - 1) {
      setAvatarIndex(avatarIndex + 1);
    } else {
      const newSeed = crypto.randomUUID();
      setAvatarSeeds([...avatarSeeds, newSeed]);
      setAvatarIndex(avatarIndex + 1);
    }
  };

  useEffect(() => {
    getFingerprint().then(setFingerprint);
  }, []);

  // Validate username format in real-time
  useEffect(() => {
    const username = formData.reserved_username;
    if (!username) {
      setUsernameValidation({ valid: true, message: '' });
      return;
    }
    const validation = validateUsername(username);
    setUsernameValidation({
      valid: validation.isValid,
      message: validation.error || '',
    });
  }, [formData.reserved_username]);

  // Check username availability with debounce
  useEffect(() => {
    const username = formData.reserved_username.trim();
    if (!username || !usernameValidation.valid) {
      setUsernameStatus({ checking: false, available: null, message: '' });
      return;
    }
    if (usernameSource === 'dice') {
      setUsernameStatus({ checking: false, available: true, message: 'Username is available' });
      return;
    }
    if (!fingerprint) return;

    setUsernameStatus({ checking: true, available: null, message: 'Checking...' });

    const timeoutId = setTimeout(async () => {
      try {
        const result = await authApi.checkUsername(username, fingerprint);
        setUsernameStatus({
          checking: false,
          available: result.available,
          message: result.available ? 'Username is available' : 'Unavailable',
        });
      } catch (error) {
        setUsernameStatus({ checking: false, available: false, message: 'Unavailable' });
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [formData.reserved_username, usernameValidation.valid, usernameSource, fingerprint]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    if (!formData.reserved_username.trim()) {
      setFieldErrors({ reserved_username: 'Reserved username is required' });
      return;
    }
    if (!usernameValidation.valid) {
      setFieldErrors({ reserved_username: usernameValidation.message });
      return;
    }
    if (usernameStatus.available === false) {
      setFieldErrors({ reserved_username: 'This username is not available' });
      return;
    }

    setLoading(true);

    try {
      const fingerprint = await getFingerprint();
      await authApi.register({
        ...formData,
        fingerprint,
        avatar_seed: currentAvatarSeed,
      });
      await authApi.login(formData.email, formData.password);

      const isChatRoute = window.location.pathname.startsWith('/chat/');
      if (!isChatRoute) {
        // Check for pending chat creation (user was creating a chat before login)
        const pendingFormData = localStorage.getItem('create_chat_form_data');
        if (pendingFormData) {
          try {
            const restored = JSON.parse(pendingFormData);
            if (restored.name && restored.name.trim()) {
              const chatRoom = await chatApi.createChat(restored);
              localStorage.removeItem('create_chat_form_data');
              router.push(chatRoom.url);
              return;
            }
          } catch {
            // Creation failed — fall through to normal redirect (modal will handle retry)
          }
        }
        router.push(redirect);
      }
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: unknown } };
      const errorData = axiosError.response?.data;

      if (typeof errorData === 'object' && errorData !== null) {
        const errorObj = errorData as Record<string, unknown>;
        const hasFieldErrors = Object.keys(errorObj).some(key =>
          ['email', 'password', 'reserved_username'].includes(key)
        );

        if (hasFieldErrors) {
          const errors: Record<string, string> = {};
          Object.entries(errorObj).forEach(([field, msgs]) => {
            const errorList = Array.isArray(msgs) ? msgs : [msgs];
            errors[field] = errorList.map(String).join('. ');
          });
          setFieldErrors(errors);
        } else if ('detail' in errorObj && typeof errorObj.detail === 'string') {
          setError(errorObj.detail);
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
    if (onSwitchToLogin) {
      onSwitchToLogin();
      return;
    }
    const path = window.location.pathname;
    // Chat page path-based auth: replace /signup with /login
    if (path.endsWith('/signup')) {
      router.replace(path.replace(/\/signup$/, '/login'));
    } else {
      const newParams = new URLSearchParams(searchParams);
      newParams.set('auth', 'login');
      router.replace(`${path}?${newParams.toString()}`);
    }
  };

  const handleSuggestUsername = async () => {
    setIsSuggestingUsername(true);
    try {
      const fingerprint = await getFingerprint();
      const result = await authApi.suggestUsername(fingerprint);
      setFormData({ ...formData, reserved_username: result.username });
      setDiceUsername(result.username);
      setUsernameSource('dice');
      setIsRotating(result.is_rotating || false);
    } catch (error) {
      console.error('Failed to suggest username:', error);
    } finally {
      setIsSuggestingUsername(false);
    }
  };

  const mt = getModalTheme(useDarkMode);
  const styles = {
    title: mt.title,
    subtitle: 'text-zinc-300',
    input: (hasError: boolean) => `${mt.input} ${hasError ? 'border-red-500' : ''}`,
    label: 'text-zinc-200',
    link: 'text-cyan-400 hover:underline hover:text-cyan-300',
    error: mt.error,
    fieldError: 'text-red-400',
    diceButton: 'bg-zinc-600 border border-zinc-500 text-zinc-50 hover:bg-zinc-500',
  };

  return (
    <>
      {!hideTitle && (
        <h1 className={`text-xl md:text-2xl font-bold ${styles.title} mb-4 text-center`}>
          {MARKETING.auth.register.title}
        </h1>
      )}

      {/* Avatar Preview */}
      <div className="flex items-center justify-center gap-3 mb-4">
        <button
          type="button"
          onClick={handleAvatarPrev}
          disabled={avatarIndex === 0}
          className="p-1.5 rounded-full text-zinc-400 hover:text-white transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
          aria-label="Previous avatar"
        >
          <ChevronLeft size={24} />
        </button>
        <img
          src={currentAvatarUrl}
          alt="Avatar preview"
          className="w-20 h-20 rounded-full bg-zinc-700"
        />
        <button
          type="button"
          onClick={handleAvatarNext}
          className="p-1.5 rounded-full text-zinc-400 hover:text-white transition-colors"
          aria-label="Next avatar"
        >
          <ChevronRight size={24} />
        </button>
      </div>

      {error && (
        <div className={`mb-6 p-4 border rounded-lg ${styles.error}`}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} autoComplete="off" className="space-y-4">
        <div>
          <label htmlFor="reg-email" className={`block text-sm font-bold ${styles.label} mb-2`}>
            {MARKETING.forms.email}
          </label>
          <input
            type="email"
            id="reg-email"
            required
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            className={`w-full px-4 py-3 rounded-xl ${styles.input(!!fieldErrors.email)} transition-colors focus:outline-none`}
            placeholder=""
          />
          {fieldErrors.email && (
            <p className={`mt-1 text-sm ${styles.fieldError}`}>{fieldErrors.email}</p>
          )}
        </div>

        <div>
          <label htmlFor="reserved_username" className={`block text-sm font-bold ${styles.label} mb-2`}>
            Reserved username <span className="text-[10px] font-normal">(across all chats)</span>
          </label>
          <div className="relative">
            <input
              type="text"
              id="reserved_username"
              required
              value={formData.reserved_username}
              onChange={(e) => {
                const newValue = e.target.value;
                setFormData({ ...formData, reserved_username: newValue });
                if (diceUsername && newValue === diceUsername) {
                  setUsernameSource('dice');
                } else {
                  setUsernameSource('manual');
                }
              }}
              className={`w-full px-4 py-3 pr-12 rounded-xl ${styles.input(!!fieldErrors.reserved_username || !usernameValidation.valid || (usernameStatus.available === false))} transition-colors focus:outline-none`}
              placeholder="Type a username"
              maxLength={15}
            />
            <button
              type="button"
              onClick={handleSuggestUsername}
              disabled={loading || isSuggestingUsername}
              className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg ${styles.diceButton} transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer`}
              title="Suggest random username"
            >
              <Dices size={20} className={isSuggestingUsername ? 'animate-spin' : ''} />
            </button>
          </div>
          {fieldErrors.reserved_username && (
            <p className={`mt-1 text-sm ${styles.fieldError}`}>{fieldErrors.reserved_username}</p>
          )}
          {!fieldErrors.reserved_username && !usernameValidation.valid && (
            <p className={`mt-1 text-sm ${styles.fieldError}`}>{usernameValidation.message}</p>
          )}
          {!fieldErrors.reserved_username && usernameValidation.valid && usernameStatus.message && (
            <p className={`mt-1 text-sm ${usernameStatus.available === true ? 'text-green-600 dark:text-green-400' : usernameStatus.available === false ? styles.fieldError : styles.subtitle}`}>
              {usernameStatus.message}
              {isRotating && usernameStatus.available && (
                <span className={`text-xs ${styles.subtitle} ml-2`}>(browsing generated options)</span>
              )}
            </p>
          )}
          {!fieldErrors.reserved_username && usernameValidation.valid && !usernameStatus.message && (
            <p className={`mt-1 text-xs ${styles.subtitle}`}>
              5-15 characters. Letters, numbers & underscores.
            </p>
          )}
        </div>

        <div>
          <label htmlFor="reg-password" className={`block text-sm font-bold ${styles.label} mb-2`}>
            {MARKETING.forms.password}
          </label>
          <input
            type="password"
            id="reg-password"
            required
            value={formData.password}
            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            className={`w-full px-4 py-3 rounded-xl ${styles.input(!!fieldErrors.password)} transition-colors focus:outline-none`}
            placeholder=""
          />
          {fieldErrors.password && (
            <p className={`mt-1 text-sm ${styles.fieldError}`}>{fieldErrors.password}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={loading}
          className={`w-full px-6 py-3 font-semibold rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${mt.primaryButton}`}
        >
          {loading ? MARKETING.auth.register.submitButtonLoading : MARKETING.auth.register.submitButton}
        </button>
      </form>

      <p className={`mt-6 text-center ${styles.subtitle}`}>
        {MARKETING.auth.register.switchToLogin}{' '}
        <button
          onClick={switchToLogin}
          className={`font-medium cursor-pointer ${styles.link}`}
        >
          {MARKETING.auth.register.switchToLoginLink}
        </button>
      </p>
    </>
  );
}

interface RegisterModalProps {
  onClose: () => void;
  theme?: 'homepage' | 'chat';
  chatTheme?: 'dark-mode';
}

export default function RegisterModal({ onClose }: RegisterModalProps) {
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
      <div className={`w-full max-w-md ${styles.container} ${mt.rounded} ${mt.shadow} p-6 md:p-8 relative max-h-[90vh] overflow-y-auto`}>
        <button
          onClick={onClose}
          className={`absolute top-4 right-4 p-2 rounded-lg transition-colors cursor-pointer ${styles.closeButton}`}
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        <RegisterFormContent onClose={onClose} />
      </div>
    </div>
  );
}
