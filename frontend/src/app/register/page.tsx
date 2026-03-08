'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { RegisterFormContent } from '@/components/RegisterModal';
import { ArrowLeft } from 'lucide-react';
import { getModalTheme } from '@/lib/modal-theme';

function RegisterPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isMobile, setIsMobile] = useState(true);

  useEffect(() => {
    const mobile = window.innerWidth < 768;
    setIsMobile(mobile);
    if (!mobile) {
      const params = new URLSearchParams(searchParams);
      params.set('auth', 'register');
      router.replace(`/?${params.toString()}`);
    }
  }, []);

  const mt = getModalTheme(true);

  const handleClose = () => {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push('/');
    }
  };

  const handleSwitchToLogin = () => {
    const params = new URLSearchParams(searchParams);
    params.delete('auth');
    const paramStr = params.toString();
    router.replace(`/login${paramStr ? `?${paramStr}` : ''}`);
  };

  if (!isMobile) return null;

  return (
    <div className={`min-h-screen ${mt.container}`}>
      <div className="flex items-center p-4 border-b border-zinc-800">
        <button
          onClick={handleClose}
          className="p-2 -ml-2 rounded-lg text-zinc-400 hover:text-white transition-colors cursor-pointer"
          aria-label="Go back"
        >
          <ArrowLeft size={20} />
        </button>
      </div>

      <div className="p-6 max-w-md mx-auto">
        <RegisterFormContent onClose={handleClose} onSwitchToLogin={handleSwitchToLogin} />
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-zinc-900" />}>
      <RegisterPageContent />
    </Suspense>
  );
}
