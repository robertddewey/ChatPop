/**
 * Centralized marketing copy for ChatPop
 * Keep all user-facing text consistent across the site
 */

export const MARKETING = {
  // Hero Section
  hero: {
    title: "Your Group Chat,",
    titleHighlight: "for Everyone",
    subtitle: "Create an instant group chat for your community and engage your audience with ChatPop",
    cta: "Start a ChatPop",
  },

  // Features
  features: {
    publicPrivate: {
      title: "Public & Private Rooms",
      description: "Control who can join your chat with access codes for private rooms",
    },
    exclusiveAccess: {
      title: "Exclusive Access",
      description: "Offer exclusive back rooms, pinned chats, and receive tips for engagement",
    },
    realTimeEngagement: {
      title: "Real-time Engagement",
      description: "Voice, video, and photo sharing to keep your audience engaged",
    },
  },

  // Authentication
  auth: {
    login: {
      title: "Welcome Back",
      subtitle: "Sign in to your account",
      submitButton: "Sign In",
      submitButtonLoading: "Signing in...",
      switchToRegister: "Don't have an account?",
      switchToRegisterLink: "Sign up",
    },
    register: {
      title: "Create Account",
      subtitle: "Sign up to start creating chat rooms",
      submitButton: "Create Account",
      submitButtonLoading: "Creating account...",
      switchToLogin: "Already have an account?",
      switchToLoginLink: "Sign in",
    },
  },

  // Form Labels
  forms: {
    email: "Email",
    password: "Password",
    passwordConfirm: "Confirm Password",
    displayName: "Display Name (optional)",
  },

  // Placeholders
  placeholders: {
    email: "you@example.com",
    password: "••••••••",
    displayName: "Your name",
  },
} as const;
