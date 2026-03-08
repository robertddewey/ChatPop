'use client';

import { useSearchParams, useRouter } from "next/navigation";
import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import dynamic from "next/dynamic";
import Header from "@/components/Header";
import LoginModal from "@/components/LoginModal";
import RegisterModal from "@/components/RegisterModal";
import CreateChatModal from "@/components/CreateChatModal";
import PhotoAnalysisModal from "@/components/PhotoAnalysisModal";
import AudioRecordingModal from "@/components/AudioRecordingModal";
import LocationSuggestionsModal from "@/components/LocationSuggestionsModal";
import { MARKETING } from "@/lib/marketing";
import { messageApi, type PhotoAnalysisResponse, type LocationAnalysisResponse, type NearbyDiscoverableChat } from "@/lib/api";
import { getFingerprint } from "@/lib/usernameStorage";
import { getModalState, clearModalState, type ModalState } from "@/lib/modalState";

// Only load DevPhotoPicker in development mode
const DevPhotoPicker = process.env.NODE_ENV === 'development'
  ? dynamic(() => import("@/components/DevPhotoPicker"), { ssr: false })
  : null;

function HomeContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const authMode = searchParams.get('auth');
  const modalMode = searchParams.get('modal');
  const [isMobile, setIsMobile] = useState(false);

  // Check for saved modal state synchronously to avoid flash
  const [restoredModalState] = useState<ModalState | null>(() => {
    if (typeof window === 'undefined') return null;
    return getModalState();
  });

  // Initialize state based on restored modal (synchronous to avoid flash)
  const [analysisResult, setAnalysisResult] = useState<PhotoAnalysisResponse | null>(() => {
    if (restoredModalState?.type === 'photo') {
      const data = restoredModalState.results as { result: PhotoAnalysisResponse };
      return data?.result || null;
    }
    return null;
  });
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showAudioModal, setShowAudioModal] = useState(() => {
    return restoredModalState?.type === 'audio';
  });
  const [showLocationModal, setShowLocationModal] = useState(() => {
    return restoredModalState?.type === 'location';
  });

  // State for restoring modals after back navigation
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [audioModalInitialState, setAudioModalInitialState] = useState<any>(() => {
    if (restoredModalState?.type === 'audio') {
      return restoredModalState.results;
    }
    return undefined;
  });
  const [locationModalInitialState, setLocationModalInitialState] = useState<{
    result: LocationAnalysisResponse;
    nearbyChats: NearbyDiscoverableChat[];
    selectedRadius: number;
  } | undefined>(() => {
    if (restoredModalState?.type === 'location') {
      return restoredModalState.results as {
        result: LocationAnalysisResponse;
        nearbyChats: NearbyDiscoverableChat[];
        selectedRadius: number;
      };
    }
    return undefined;
  });

  // Persistent refs for file inputs to prevent garbage collection
  const cameraInputRef = useRef<HTMLInputElement | null>(null);
  const libraryInputRef = useRef<HTMLInputElement | null>(null);

  // Dev mode photo picker state (only in development)
  const [showDevPhotoPicker, setShowDevPhotoPicker] = useState(false);
  const longPressTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isDev = process.env.NODE_ENV === 'development';

  // Shared photo processing logic
  const processPhoto = useCallback(async (file: File, source: 'camera' | 'library' | 'dev-cache') => {
    const emoji = source === 'camera' ? '📸' : source === 'library' ? '🖼️' : '🔄';
    const label = source === 'camera' ? 'Camera photo captured' : source === 'library' ? 'Photo selected from library' : 'Dev cache photo selected';
    console.log(`${emoji} ${label}:`, file.name, file.type, `${(file.size / 1024).toFixed(1)}KB`);

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

    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      console.error('❌ Photo analysis failed:', error.response?.data || error.message);
      setIsAnalyzing(false);
      alert(`Photo analysis failed: ${error.response?.data?.detail || error.message}`);
    }
  }, []);

  // Initialize persistent file inputs on mount
  useEffect(() => {
    // Create camera input (with capture attribute for direct camera access)
    const cameraInput = document.createElement('input');
    cameraInput.type = 'file';
    cameraInput.accept = 'image/*';
    cameraInput.capture = 'environment';
    cameraInput.style.display = 'none';
    cameraInput.id = 'camera-input-persistent';
    document.body.appendChild(cameraInput);
    cameraInputRef.current = cameraInput;

    // Create library input (no capture = allows library selection)
    const libraryInput = document.createElement('input');
    libraryInput.type = 'file';
    libraryInput.accept = 'image/*';
    libraryInput.style.display = 'none';
    libraryInput.id = 'library-input-persistent';
    document.body.appendChild(libraryInput);
    libraryInputRef.current = libraryInput;

    // Cleanup on unmount
    return () => {
      if (cameraInputRef.current) {
        document.body.removeChild(cameraInputRef.current);
        cameraInputRef.current = null;
      }
      if (libraryInputRef.current) {
        document.body.removeChild(libraryInputRef.current);
        libraryInputRef.current = null;
      }
    };
  }, []);

  // Attach event handlers separately to avoid stale closure issues
  useEffect(() => {
    const cameraInput = cameraInputRef.current;
    const libraryInput = libraryInputRef.current;

    const handleCameraChange = (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        processPhoto(file, 'camera');
      }
      // Reset input so same file can be selected again
      if (cameraInput) cameraInput.value = '';
    };

    const handleLibraryChange = (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        processPhoto(file, 'library');
      }
      // Reset input so same file can be selected again
      if (libraryInput) libraryInput.value = '';
    };

    if (cameraInput) {
      cameraInput.addEventListener('change', handleCameraChange);
    }
    if (libraryInput) {
      libraryInput.addEventListener('change', handleLibraryChange);
    }

    return () => {
      if (cameraInput) {
        cameraInput.removeEventListener('change', handleCameraChange);
      }
      if (libraryInput) {
        libraryInput.removeEventListener('change', handleLibraryChange);
      }
    };
  }, [processPhoto]);

  useEffect(() => {
    // Detect if device is mobile
    const checkMobile = () => {
      setIsMobile(/iPhone|iPad|iPod|Android/i.test(navigator.userAgent));
    };
    checkMobile();

    // Defensive cleanup: ensure body overflow is reset when homepage loads
    // Skip if a modal is being restored (modal will set overflow: hidden on its own mount)
    if (!restoredModalState) {
      document.body.style.overflow = '';
    }
  }, []);

  // On mobile, redirect auth/create URL params to full pages
  useEffect(() => {
    if (!isMobile) return;
    if (authMode === 'login') {
      const params = new URLSearchParams(searchParams);
      params.delete('auth');
      const redirect = params.get('redirect');
      const newParams = new URLSearchParams();
      if (redirect) newParams.set('redirect', redirect);
      router.replace(`/login${newParams.toString() ? `?${newParams.toString()}` : ''}`);
    } else if (authMode === 'register') {
      const params = new URLSearchParams(searchParams);
      params.delete('auth');
      const redirect = params.get('redirect');
      const newParams = new URLSearchParams();
      if (redirect) newParams.set('redirect', redirect);
      router.replace(`/register${newParams.toString() ? `?${newParams.toString()}` : ''}`);
    } else if (modalMode === 'create') {
      router.replace('/create');
    }
  }, [isMobile, authMode, modalMode]);

  const closeModal = () => {
    router.push('/', { scroll: false });
  };

  const closeAnalysisModal = () => {
    setAnalysisResult(null);
    setIsAnalyzing(false);
    clearModalState(); // Clear saved state when user manually closes
  };

  const openCreateModal = () => {
    if (isMobile) {
      router.push('/create');
    } else {
      router.push('/?modal=create', { scroll: false });
    }
  };

  const handleCameraClick = () => {
    if (isMobile && cameraInputRef.current) {
      cameraInputRef.current.click();
    }
  };

  const handleLibraryClick = () => {
    if (isMobile && libraryInputRef.current) {
      libraryInputRef.current.click();
    }
  };

  // Dev mode: Long-press handlers for camera button
  const handleCameraLongPressStart = (e: React.TouchEvent | React.MouseEvent) => {
    if (!isDev || !isMobile) return;

    // Prevent text selection / context menu on long press
    e.preventDefault();

    longPressTimerRef.current = setTimeout(() => {
      console.log('📸 [DEV] Long press detected - opening photo picker');
      setShowDevPhotoPicker(true);
    }, 1500); // 1.5 second long press
  };

  const handleCameraLongPressEnd = () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  };

  // Dev mode: Handle photo selected from dev picker
  const handleDevPhotoSelect = (file: File) => {
    setShowDevPhotoPicker(false);
    processPhoto(file, 'dev-cache');
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
                  onMouseDown={handleCameraLongPressStart}
                  onMouseUp={handleCameraLongPressEnd}
                  onMouseLeave={handleCameraLongPressEnd}
                  onTouchStart={handleCameraLongPressStart}
                  onTouchEnd={handleCameraLongPressEnd}
                  onTouchCancel={handleCameraLongPressEnd}
                  onContextMenu={(e) => isDev && e.preventDefault()}
                  className={`inline-flex items-center justify-center w-14 h-14 rounded-full transition-all shadow-lg select-none ${
                    isMobile
                      ? 'bg-white text-gray-900 hover:bg-gray-100 transform hover:scale-105 shadow-lg hover:shadow-xl cursor-pointer'
                      : 'bg-gray-600 text-gray-400 cursor-not-allowed opacity-50'
                  }`}
                  style={{ WebkitTouchCallout: 'none' }}
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
                  onMouseDown={handleCameraLongPressStart}
                  onMouseUp={handleCameraLongPressEnd}
                  onMouseLeave={handleCameraLongPressEnd}
                  onTouchStart={handleCameraLongPressStart}
                  onTouchEnd={handleCameraLongPressEnd}
                  onTouchCancel={handleCameraLongPressEnd}
                  onContextMenu={(e) => isDev && e.preventDefault()}
                  className={`inline-flex items-center justify-center w-14 h-14 rounded-full transition-all shadow-lg select-none ${
                    isMobile
                      ? 'bg-white text-gray-900 hover:bg-gray-100 transform hover:scale-105 shadow-lg hover:shadow-xl cursor-pointer'
                      : 'bg-gray-600 text-gray-400 cursor-not-allowed opacity-50'
                  }`}
                  style={{ WebkitTouchCallout: 'none' }}
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

      {/* Modals (desktop only — mobile uses full pages) */}
      {!isMobile && authMode === 'login' && <LoginModal onClose={closeModal} />}
      {!isMobile && authMode === 'register' && <RegisterModal onClose={closeModal} />}
      {!isMobile && modalMode === 'create' && <CreateChatModal onClose={closeModal} />}
      {(isAnalyzing || analysisResult) && (
        <PhotoAnalysisModal
          result={analysisResult}
          isLoading={isAnalyzing}
          onClose={closeAnalysisModal}
        />
      )}
      {showAudioModal && (
        <AudioRecordingModal
          onClose={() => {
            setShowAudioModal(false);
            setAudioModalInitialState(undefined);
            clearModalState(); // Clear saved state when user manually closes
          }}
          initialState={audioModalInitialState}
        />
      )}
      {showLocationModal && (
        <LocationSuggestionsModal
          onClose={() => {
            setShowLocationModal(false);
            setLocationModalInitialState(undefined);
            clearModalState(); // Clear saved state when user manually closes
          }}
          initialState={locationModalInitialState}
        />
      )}
      {/* Dev Mode Photo Picker */}
      {isDev && DevPhotoPicker && showDevPhotoPicker && (
        <DevPhotoPicker
          onSelect={handleDevPhotoSelect}
          onClose={() => setShowDevPhotoPicker(false)}
        />
      )}
    </div>
  );
}

// Wrap in Suspense for Next.js static generation with useSearchParams
export default function Home() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-b from-gray-900 from-5% via-purple-900 via-30% to-[#404eed] to-60% flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    }>
      <HomeContent />
    </Suspense>
  );
}
