'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { LoginFormContent } from '@/components/LoginModal';
import { ArrowLeft } from 'lucide-react';
import { getModalTheme } from '@/lib/modal-theme';

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isMobile, setIsMobile] = useState(true); // Default true to avoid flash

  useEffect(() => {
    // On desktop, redirect to homepage modal
    const mobile = window.innerWidth < 768;
    setIsMobile(mobile);
    if (!mobile) {
      const params = new URLSearchParams(searchParams);
      params.set('auth', 'login');
      router.replace(`/?${params.toString()}`);
    }
  }, []);

  const mt = getModalTheme(true);

  const handleClose = () => {
    // Go back if there's history, otherwise go home
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push('/');
    }
  };

  const handleSwitchToRegister = () => {
    const params = new URLSearchParams(searchParams);
    params.delete('auth');
    const paramStr = params.toString();
    router.replace(`/register${paramStr ? `?${paramStr}` : ''}`);
  };

  if (!isMobile) return null;

  return (
    <div className={`min-h-screen ${mt.container}`}>
      {/* Header with back button */}
      <div className="flex items-center p-4 border-b border-zinc-800">
        <button
          onClick={handleClose}
          className="p-2 -ml-2 rounded-lg text-zinc-400 hover:text-white transition-colors cursor-pointer"
          aria-label="Go back"
        >
          <ArrowLeft size={20} />
        </button>
      </div>

      {/* Form content — normal document flow, keyboard-safe */}
      <div className="p-6 max-w-md mx-auto">
        <LoginFormContent onClose={handleClose} onSwitchToRegister={handleSwitchToRegister} />
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-zinc-900" />}>
      <LoginPageContent />
    </Suspense>
  );
}
