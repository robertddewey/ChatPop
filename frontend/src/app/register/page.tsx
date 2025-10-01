'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { authApi } from '@/lib/api';
import Header from '@/components/Header';

export default function RegisterPage() {
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
        // Check if it's field-specific errors
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 dark:from-gray-900 dark:to-gray-800">
      <Header />

      <main className="container mx-auto px-4 py-12 max-w-md">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Create Account
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-8">
            Sign up to start creating chat rooms
          </p>

          {error && (
            <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Email
              </label>
              <input
                type="email"
                id="email"
                required
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white ${
                  fieldErrors.email ? 'border-red-500 dark:border-red-500' : 'border-gray-300 dark:border-gray-600'
                }`}
                placeholder="you@example.com"
              />
              {fieldErrors.email && (
                <p className="mt-1 text-sm text-red-600 dark:text-red-400">{fieldErrors.email}</p>
              )}
            </div>

            <div>
              <label htmlFor="display_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Display Name (optional)
              </label>
              <input
                type="text"
                id="display_name"
                value={formData.display_name}
                onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                placeholder="Your name"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Password
              </label>
              <input
                type="password"
                id="password"
                required
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white ${
                  fieldErrors.password ? 'border-red-500 dark:border-red-500' : 'border-gray-300 dark:border-gray-600'
                }`}
                placeholder="••••••••"
              />
              {fieldErrors.password && (
                <p className="mt-1 text-sm text-red-600 dark:text-red-400">{fieldErrors.password}</p>
              )}
            </div>

            <div>
              <label htmlFor="password_confirm" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Confirm Password
              </label>
              <input
                type="password"
                id="password_confirm"
                required
                value={formData.password_confirm}
                onChange={(e) => setFormData({ ...formData, password_confirm: e.target.value })}
                className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white ${
                  fieldErrors.password_confirm ? 'border-red-500 dark:border-red-500' : 'border-gray-300 dark:border-gray-600'
                }`}
                placeholder="••••••••"
              />
              {fieldErrors.password_confirm && (
                <p className="mt-1 text-sm text-red-600 dark:text-red-400">{fieldErrors.password_confirm}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating account...' : 'Create Account'}
            </button>
          </form>

          <p className="mt-6 text-center text-gray-600 dark:text-gray-400">
            Already have an account?{' '}
            <Link
              href={`/login${redirect !== '/' ? `?redirect=${encodeURIComponent(redirect)}` : ''}`}
              className="text-purple-600 dark:text-purple-400 hover:underline font-medium"
            >
              Sign in
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
