/**
 * Centralized marketing copy for ChatPop
 * Keep all user-facing text consistent across the site
 */

export const MARKETING = {
  // Hero Section
  hero: {
    title: "Your Group Chat,",
    titleHighlight: "for Everyone.",
    badge: "No App Needed",
    subtitle: "Create an instant group chat for your community and engage your audience with ChatPop. Share the link and chat.",
    cta: "Start a ChatPop",
  },

  // Features
  features: {
    noAppNeeded: {
      title: "No App Required",
      description: "Your audience just needs the link - no app download or registration needed to join and chat",
    },
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
      title: "Log in to ChatPop",
      subtitle: "Log in to your account",
      submitButton: "Log in",
      submitButtonLoading: "Logging in...",
      switchToRegister: "Don't have an account?",
      switchToRegisterLink: "Sign up",
    },
    register: {
      title: "Join ChatPop",
      subtitle: "Sign up to start creating chat rooms",
      submitButton: "Sign up",
      submitButtonLoading: "Creating account...",
      switchToLogin: "Already have an account?",
      switchToLoginLink: "Log in",
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
