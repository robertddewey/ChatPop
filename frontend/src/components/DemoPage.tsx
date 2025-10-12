'use client';

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { DEMO_THEMES, DemoTheme } from "@/lib/demo-themes";
import { MARKETING } from "@/lib/marketing";
import Header from "@/components/Header";
import LoginModal from "@/components/LoginModal";
import RegisterModal from "@/components/RegisterModal";
import CreateChatModal from "@/components/CreateChatModal";

interface DemoPageProps {
  themeId: number;
  authMode?: string | null;
  modalMode?: string | null;
}

export default function DemoPage({ themeId, authMode, modalMode }: DemoPageProps) {
  const router = useRouter();
  const theme = DEMO_THEMES.find(t => t.id === themeId) || DEMO_THEMES[0];

  const closeModal = () => {
    // If themeId is 1, go to homepage, otherwise go to the theme page
    router.push(themeId === 1 ? '/' : `/${themeId}`);
  };

  const openCreateModal = () => {
    // If themeId is 1, use homepage URL, otherwise use theme page URL
    router.push(themeId === 1 ? '/?modal=create' : `/${themeId}?modal=create`);
  };

  // Set theme-color for browser chrome
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const updateThemeColor = () => {
      const themeColor = theme.themeColorDark;

      let metaTag = document.querySelector('meta[name="theme-color"]');
      if (!metaTag) {
        metaTag = document.createElement('meta');
        metaTag.setAttribute('name', 'theme-color');
        document.head.appendChild(metaTag);
      }
      metaTag.setAttribute('content', themeColor);
    };

    updateThemeColor();
  }, [theme]);

  return (
    <div className={`min-h-screen ${theme.background}`}>
      <Header backgroundClass={theme.headerBackground} />

      {/* Hero Section */}
      <main className="container mx-auto px-4 py-8 md:py-20">
        <div className="max-w-4xl mx-auto text-center">
          <div className="mb-8">
            <h2 className="text-6xl md:text-7xl font-black text-white tracking-[-0.03em] leading-[0.95]" style={{ fontWeight: 900, WebkitTextStroke: '1px white' }}>
              {MARKETING.hero.title}
              <span className={`block bg-gradient-to-r ${theme.titleGradient} bg-clip-text text-transparent pb-3`}>
                {MARKETING.hero.titleHighlight}
              </span>
            </h2>
          </div>

          {/* Badge */}
          <div className="mb-8">
            <span className={`inline-block px-4 py-2 ${theme.badgeBackground} ${theme.badgeText} rounded-full text-sm font-bold tracking-wide`}>
              {MARKETING.hero.badge}
            </span>
          </div>

          <p className="text-lg md:text-xl text-gray-300 mb-12 max-w-2xl mx-auto font-medium">
            {MARKETING.hero.subtitle}
          </p>

          {/* Main CTA */}
          <button
            onClick={openCreateModal}
            className="inline-block px-8 py-4 text-lg font-bold bg-white text-gray-900 rounded-full hover:bg-gray-100 transition-all transform hover:scale-105 shadow-lg hover:shadow-xl"
          >
            {MARKETING.hero.cta}
          </button>

          {/* Features Grid */}
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mt-20">
            <div className={`p-6 ${theme.cardBackground} rounded-2xl backdrop-blur-sm`}>
              <div className={`w-14 h-14 ${theme.cardIconBackground} rounded-xl flex items-center justify-center mb-4 mx-auto`}>
                <svg className={`w-7 h-7 ${theme.cardIconColor}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-2">{MARKETING.features.noAppNeeded.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                {MARKETING.features.noAppNeeded.description}
              </p>
            </div>

            <div className={`p-6 ${theme.cardBackground} rounded-2xl backdrop-blur-sm`}>
              <div className={`w-14 h-14 ${theme.cardIconBackground} rounded-xl flex items-center justify-center mb-4 mx-auto`}>
                <svg className={`w-7 h-7 ${theme.cardIconColor}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-2">{MARKETING.features.publicPrivate.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                {MARKETING.features.publicPrivate.description}
              </p>
            </div>

            <div className={`p-6 ${theme.cardBackground} rounded-2xl backdrop-blur-sm`}>
              <div className={`w-14 h-14 ${theme.cardIconBackground} rounded-xl flex items-center justify-center mb-4 mx-auto`}>
                <svg className={`w-7 h-7 ${theme.cardIconColor}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-2">{MARKETING.features.exclusiveAccess.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                {MARKETING.features.exclusiveAccess.description}
              </p>
            </div>

            <div className={`p-6 ${theme.cardBackground} rounded-2xl backdrop-blur-sm`}>
              <div className={`w-14 h-14 ${theme.cardIconBackground} rounded-xl flex items-center justify-center mb-4 mx-auto`}>
                <svg className={`w-7 h-7 ${theme.cardIconColor}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-2">{MARKETING.features.realTimeEngagement.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
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
