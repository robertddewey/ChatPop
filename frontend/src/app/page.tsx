'use client';

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import Header from "@/components/Header";
import LoginModal from "@/components/LoginModal";
import RegisterModal from "@/components/RegisterModal";
import CreateChatModal from "@/components/CreateChatModal";
import { MARKETING } from "@/lib/marketing";

export default function Home() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const authMode = searchParams.get('auth');
  const modalMode = searchParams.get('modal');

  const closeModal = () => {
    router.push('/');
  };

  const openCreateModal = () => {
    router.push('/?modal=create');
  };

  // Set theme-color for homepage
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const updateThemeColor = () => {
      // Detect dark mode preference
      const isDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
      // Match homepage gradient colors (purple-50 for light, gray-900 for dark)
      const themeColor = isDarkMode ? '#111827' : '#faf5ff';

      // Find or create theme-color meta tag
      let metaTag = document.querySelector('meta[name="theme-color"]');
      if (!metaTag) {
        metaTag = document.createElement('meta');
        metaTag.setAttribute('name', 'theme-color');
        document.head.appendChild(metaTag);
      }
      metaTag.setAttribute('content', themeColor);
    };

    // Update initially
    updateThemeColor();

    // Listen for dark mode changes
    const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleDarkModeChange = () => updateThemeColor();
    darkModeQuery.addEventListener('change', handleDarkModeChange);

    return () => {
      darkModeQuery.removeEventListener('change', handleDarkModeChange);
    };
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 dark:from-gray-900 dark:to-gray-800">
      <Header />

      {/* Hero Section */}
      <main className="container mx-auto px-4 py-8 md:py-20">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-5xl md:text-6xl font-bold text-gray-900 dark:text-white mb-4">
            {MARKETING.hero.title}
            <span className="block bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
              {MARKETING.hero.titleHighlight}
            </span>
          </h2>

          {/* Badge */}
          <div className="mb-6">
            <span className="inline-block px-4 py-2 bg-gradient-to-r from-purple-100 to-blue-100 dark:from-purple-900/30 dark:to-blue-900/30 text-purple-700 dark:text-purple-300 rounded-full text-sm font-semibold">
              {MARKETING.hero.badge}
            </span>
          </div>

          <p className="text-base md:text-xl text-gray-600 dark:text-gray-300 mb-12 max-w-2xl mx-auto">
            {MARKETING.hero.subtitle}
          </p>

          {/* Main CTA */}
          <button
            onClick={openCreateModal}
            className="inline-block px-8 py-4 text-lg font-semibold bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-full hover:from-purple-700 hover:to-blue-700 transition-all transform hover:scale-105 shadow-lg hover:shadow-xl"
          >
            {MARKETING.hero.cta}
          </button>

          {/* Features Grid */}
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8 mt-20">
            <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-md">
              <div className="w-12 h-12 bg-cyan-100 dark:bg-cyan-900/30 rounded-lg flex items-center justify-center mb-4 mx-auto">
                <svg className="w-6 h-6 text-cyan-600 dark:text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{MARKETING.features.noAppNeeded.title}</h3>
              <p className="text-gray-600 dark:text-gray-400">
                {MARKETING.features.noAppNeeded.description}
              </p>
            </div>

            <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-md">
              <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/30 rounded-lg flex items-center justify-center mb-4 mx-auto">
                <svg className="w-6 h-6 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{MARKETING.features.publicPrivate.title}</h3>
              <p className="text-gray-600 dark:text-gray-400">
                {MARKETING.features.publicPrivate.description}
              </p>
            </div>

            <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-md">
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center mb-4 mx-auto">
                <svg className="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{MARKETING.features.exclusiveAccess.title}</h3>
              <p className="text-gray-600 dark:text-gray-400">
                {MARKETING.features.exclusiveAccess.description}
              </p>
            </div>

            <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-md">
              <div className="w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center mb-4 mx-auto">
                <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{MARKETING.features.realTimeEngagement.title}</h3>
              <p className="text-gray-600 dark:text-gray-400">
                {MARKETING.features.realTimeEngagement.description}
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Modals */}
      {authMode === 'login' && <LoginModal onClose={closeModal} />}
      {authMode === 'register' && <RegisterModal onClose={closeModal} />}
      {modalMode === 'create' && <CreateChatModal onClose={closeModal} />}
    </div>
  );
}
