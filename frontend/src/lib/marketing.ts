/**
 * Centralized marketing copy for ChatPop
 * Keep all user-facing text consistent across the site
 */

export const MARKETING = {
  // Hero Section
  hero: {
    title: "Group Chat.",
    titleHighlight: "For Everyone & Everything.",
    badge: "No App Needed",
    subtitle: "See a movie poster? Snap it and chat. Have a community? Create a room. Just share the link and start chatting.",
    cta: "Start a ChatPop",
  },

  // Features
  features: {
    everythingIsChat: {
      title: "Everything is a Chat",
      description: "Snap a photo of things to chat about. Movies, music, places, books, cats",
    },
    noAppNeeded: {
      title: "No App Required",
      description: "Just a photo or a link. No app download is required to join the conversation",
    },
    publicPrivate: {
      title: "Public & Private",
      description: "Control who can join your chat by adding a passcode or paid access",
    },
    realTimeEngagement: {
      title: "Group Sharing",
      description: "Voice, video, and photo streams with your group or community",
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
