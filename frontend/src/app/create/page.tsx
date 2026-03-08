'use client';

import { useEffect, useState, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { CreateChatFormContent } from '@/components/CreateChatModal';
import { ArrowLeft } from 'lucide-react';
import { getModalTheme } from '@/lib/modal-theme';

function CreatePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isMobile, setIsMobile] = useState(true);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mobile = window.innerWidth < 768;
    setIsMobile(mobile);
    if (!mobile) {
      router.replace('/?modal=create');
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
        <h1 className={`text-lg font-bold ${mt.title} ml-2`}>
          Room Settings
        </h1>
      </div>

      <div ref={scrollContainerRef} className="p-6 max-w-md mx-auto">
        <CreateChatFormContent onClose={handleClose} scrollContainerRef={scrollContainerRef} />
      </div>
    </div>
  );
}

export default function CreatePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-zinc-900" />}>
      <CreatePageContent />
    </Suspense>
  );
}
