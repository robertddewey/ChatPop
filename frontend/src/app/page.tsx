'use client';

import { useSearchParams, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import Header from "@/components/Header";
import LoginModal from "@/components/LoginModal";
import RegisterModal from "@/components/RegisterModal";
import CreateChatModal from "@/components/CreateChatModal";
import PhotoAnalysisModal from "@/components/PhotoAnalysisModal";
import AudioRecordingModal from "@/components/AudioRecordingModal";
import LocationSuggestionsModal from "@/components/LocationSuggestionsModal";
import { MARKETING } from "@/lib/marketing";
import { messageApi } from "@/lib/api";
import { getFingerprint } from "@/lib/usernameStorage";

export default function Home() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const authMode = searchParams.get('auth');
  const modalMode = searchParams.get('modal');
  const [isMobile, setIsMobile] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showAudioModal, setShowAudioModal] = useState(false);
  const [showLocationModal, setShowLocationModal] = useState(false);

  useEffect(() => {
    // Detect if device is mobile
    const checkMobile = () => {
      setIsMobile(/iPhone|iPad|iPod|Android/i.test(navigator.userAgent));
    };
    checkMobile();
  }, []);

  const closeModal = () => {
    router.push('/', { scroll: false });
  };

  const closeAnalysisModal = () => {
    setAnalysisResult(null);
    setIsAnalyzing(false);
  };

  const openCreateModal = () => {
    router.push('/?modal=create', { scroll: false });
  };

  const handleCameraClick = () => {
    if (isMobile) {
      // Create a hidden file input to trigger camera
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*'; // Accept images only
      input.capture = 'environment'; // Force camera mode (rear camera)

      input.onchange = async (e) => {
        const file = (e.target as HTMLInputElement).files?.[0];
        if (file) {
          console.log('📸 Photo captured from camera:', file.name, file.type, `${(file.size / 1024).toFixed(1)}KB`);

          try {
            // Show modal with loading state immediately
            setIsAnalyzing(true);
            setAnalysisResult(null);

            // Get fingerprint for tracking
            const fingerprint = await getFingerprint();

            // Analyze photo
            const result = await messageApi.analyzePhoto(file, fingerprint);
            console.log('✅ Analysis complete:', result);

            // Update modal with result
            setAnalysisResult(result);
            setIsAnalyzing(false);

          } catch (err: any) {
            console.error('❌ Photo analysis failed:', err.response?.data || err.message);
            setIsAnalyzing(false);
            // TODO: Show error in modal or toast notification
            alert(`Photo analysis failed: ${err.response?.data?.detail || err.message}`);
          }
        }
      };

      input.click();
    }
  };

  const handleLibraryClick = () => {
    if (isMobile) {
      // Create a hidden file input to trigger photo library
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*'; // Accept images only
      // No capture attribute = allows library selection

      input.onchange = async (e) => {
        const file = (e.target as HTMLInputElement).files?.[0];
        if (file) {
          console.log('🖼️ Photo selected from library:', file.name, file.type, `${(file.size / 1024).toFixed(1)}KB`);

          try {
            // Show modal with loading state immediately
            setIsAnalyzing(true);
            setAnalysisResult(null);

            // Get fingerprint for tracking
            const fingerprint = await getFingerprint();

            // Analyze photo
            const result = await messageApi.analyzePhoto(file, fingerprint);
            console.log('✅ Analysis complete:', result);

            // Update modal with result
            setAnalysisResult(result);
            setIsAnalyzing(false);

          } catch (err: any) {
            console.error('❌ Photo analysis failed:', err.response?.data || err.message);
            setIsAnalyzing(false);
            // TODO: Show error in modal or toast notification
            alert(`Photo analysis failed: ${err.response?.data?.detail || err.message}`);
          }
        }
      };

      input.click();
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 from-5% via-purple-900 via-30% to-[#404eed] to-60%">
      <Header backgroundClass="bg-gray-900/80" />

      {/* Hero Section */}
      <main className="container mx-auto px-4 py-8 md:py-20">
        <div className="max-w-5xl mx-auto text-center">
          <div className="mb-8">
            <h2 className="text-6xl md:text-7xl font-black text-white tracking-[-0.03em] leading-[0.95]" style={{ fontWeight: 900, WebkitTextStroke: '1px white' }}>
              {MARKETING.hero.title}
              <span className="block text-white pb-3">
                {MARKETING.hero.titleHighlight}
              </span>
            </h2>
          </div>

          {/* Badge */}
          <div className="mb-8">
            <span className="inline-block px-4 py-2 bg-white/10 text-white rounded-full text-sm font-bold tracking-wide">
              {MARKETING.hero.badge}
            </span>
          </div>

          <p className="text-lg md:text-xl text-gray-300 mb-12 max-w-2xl mx-auto font-medium">
            {MARKETING.hero.subtitle}
          </p>

          {/* Main CTA */}
          <div className="flex flex-col items-center gap-6">
            {/* Start a ChatPop Button */}
            <button
              onClick={openCreateModal}
              className="inline-block px-8 py-4 text-lg font-bold bg-white text-gray-900 rounded-full hover:bg-gray-100 transition-all transform hover:scale-105 shadow-lg hover:shadow-xl cursor-pointer"
            >
              {MARKETING.hero.cta}
            </button>

            {/* Media Buttons Row */}
            <div className="flex items-center justify-center gap-4">
              {/* Camera Button */}
              <div className="relative group">
                <button
                  onClick={handleCameraClick}
                  disabled={!isMobile}
                  className={`inline-flex items-center justify-center w-14 h-14 rounded-full transition-all shadow-lg ${
                    isMobile
                      ? 'bg-white text-gray-900 hover:bg-gray-100 transform hover:scale-105 shadow-lg hover:shadow-xl cursor-pointer'
                      : 'bg-gray-600 text-gray-400 cursor-not-allowed opacity-50'
                  }`}
                >
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </button>

                {/* Desktop tooltip */}
                {!isMobile && (
                  <div className="absolute top-full mt-2 left-1/2 transform -translate-x-1/2 px-3 py-2 bg-gray-800 text-white text-sm rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    Mobile only
                  </div>
                )}
              </div>

              {/* Photo Library Button */}
              <div className="relative group">
                <button
                  onClick={handleLibraryClick}
                  disabled={!isMobile}
                  className={`inline-flex items-center justify-center w-14 h-14 rounded-full transition-all shadow-lg ${
                    isMobile
                      ? 'bg-white text-gray-900 hover:bg-gray-100 transform hover:scale-105 shadow-lg hover:shadow-xl cursor-pointer'
                      : 'bg-gray-600 text-gray-400 cursor-not-allowed opacity-50'
                  }`}
                >
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </button>

                {/* Desktop tooltip */}
                {!isMobile && (
                  <div className="absolute top-full mt-2 left-1/2 transform -translate-x-1/2 px-3 py-2 bg-gray-800 text-white text-sm rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    Mobile only
                  </div>
                )}
              </div>

              {/* Microphone/Music Button */}
              <div className="relative group">
                <button
                  onClick={() => isMobile && setShowAudioModal(true)}
                  disabled={!isMobile}
                  className={`inline-flex items-center justify-center w-14 h-14 rounded-full transition-all shadow-lg ${
                    isMobile
                      ? 'bg-white text-gray-900 hover:bg-gray-100 transform hover:scale-105 shadow-lg hover:shadow-xl cursor-pointer'
                      : 'bg-gray-600 text-gray-400 cursor-not-allowed opacity-50'
                  }`}
                >
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                  </svg>
                </button>

                {/* Desktop tooltip */}
                {!isMobile && (
                  <div className="absolute top-full mt-2 left-1/2 transform -translate-x-1/2 px-3 py-2 bg-gray-800 text-white text-sm rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    Mobile only
                  </div>
                )}
              </div>

              {/* Location Button */}
              <div className="relative group">
                <button
                  onClick={() => isMobile && setShowLocationModal(true)}
                  disabled={!isMobile}
                  className={`inline-flex items-center justify-center w-14 h-14 rounded-full transition-all shadow-lg ${
                    isMobile
                      ? 'bg-white text-gray-900 hover:bg-gray-100 transform hover:scale-105 shadow-lg hover:shadow-xl cursor-pointer'
                      : 'bg-gray-600 text-gray-400 cursor-not-allowed opacity-50'
                  }`}
                >
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </button>

                {/* Desktop tooltip */}
                {!isMobile && (
                  <div className="absolute top-full mt-2 left-1/2 transform -translate-x-1/2 px-3 py-2 bg-gray-800 text-white text-sm rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    Mobile only
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Features Grid */}
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mt-20">
            <div className="p-6 bg-white/5 border border-white/10 rounded-2xl backdrop-blur-sm">
              <div className="w-14 h-14 bg-white/10 rounded-xl flex items-center justify-center mb-4 mx-auto">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-2">{MARKETING.features.everythingIsChat.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                {MARKETING.features.everythingIsChat.description}
              </p>
            </div>

            <div className="p-6 bg-white/5 border border-white/10 rounded-2xl backdrop-blur-sm">
              <div className="w-14 h-14 bg-white/10 rounded-xl flex items-center justify-center mb-4 mx-auto">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-2">{MARKETING.features.noAppNeeded.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                {MARKETING.features.noAppNeeded.description}
              </p>
            </div>

            <div className="p-6 bg-white/5 border border-white/10 rounded-2xl backdrop-blur-sm">
              <div className="w-14 h-14 bg-white/10 rounded-xl flex items-center justify-center mb-4 mx-auto">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-2">{MARKETING.features.publicPrivate.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                {MARKETING.features.publicPrivate.description}
              </p>
            </div>

            <div className="p-6 bg-white/5 border border-white/10 rounded-2xl backdrop-blur-sm">
              <div className="w-14 h-14 bg-white/10 rounded-xl flex items-center justify-center mb-4 mx-auto">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
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
      {(isAnalyzing || analysisResult) && (
        <PhotoAnalysisModal
          result={analysisResult}
          isLoading={isAnalyzing}
          onClose={closeAnalysisModal}
        />
      )}
      {showAudioModal && (
        <AudioRecordingModal onClose={() => setShowAudioModal(false)} />
      )}
      {showLocationModal && (
        <LocationSuggestionsModal onClose={() => setShowLocationModal(false)} />
      )}
    </div>
  );
}
