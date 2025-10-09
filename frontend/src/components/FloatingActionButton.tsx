'use client';

import React, { useState, useEffect, type ReactNode } from 'react';
import { LucideIcon } from 'lucide-react';

export interface FloatingActionButtonProps {
  /** Icon component from lucide-react */
  icon: LucideIcon;
  /** Alternative icon to show when toggled (optional) */
  toggledIcon?: LucideIcon;
  /** Click handler */
  onClick: () => void;
  /** Whether this button represents a toggled state (e.g., opened panel) */
  isToggled?: boolean;
  /** Show notification badge */
  hasNotification?: boolean;
  /** Position on screen */
  position?: 'right' | 'left';
  /** Vertical position */
  verticalPosition?: 'center' | 'top' | 'bottom';
  /** Optional custom positioning (overrides position props) */
  customPosition?: string;
  /** Accessibility label */
  ariaLabel: string;
  /** Toggled state accessibility label */
  toggledAriaLabel?: string;
  /** Theme/design variant */
  design?: 'dark-mode' | 'pink-dream' | 'ocean-blue' | 'light-mode';
  /** Show initial bounce animation on mount */
  initialBounce?: boolean;
  /** Custom class names to add */
  className?: string;
}

export default function FloatingActionButton({
  icon: Icon,
  toggledIcon: ToggledIcon,
  onClick,
  isToggled = false,
  hasNotification = false,
  position = 'right',
  verticalPosition = 'center',
  customPosition,
  ariaLabel,
  toggledAriaLabel,
  design = 'dark-mode',
  initialBounce = false,
  className = '',
}: FloatingActionButtonProps) {
  const [showInitialBounce, setShowInitialBounce] = useState(false);

  useEffect(() => {
    if (initialBounce) {
      // Trigger bounce animation after component mounts
      const timer = setTimeout(() => {
        setShowInitialBounce(true);
        // Remove the animation class after it completes
        const removeTimer = setTimeout(() => setShowInitialBounce(false), 1000);
        return () => clearTimeout(removeTimer);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [initialBounce]);

  // Design-specific styling
  const getDesignStyles = () => {
    switch (design) {
      case 'pink-dream':
        return {
          baseClasses: 'p-3 rounded-2xl',
          defaultColors: 'bg-gradient-to-br from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 text-white',
          toggledColors: 'bg-gradient-to-br from-pink-100 to-pink-200 dark:from-indigo-800 dark:to-indigo-900 hover:from-pink-200 hover:to-pink-300 dark:hover:from-indigo-700 dark:hover:to-indigo-800 text-pink-900 dark:text-white',
          shadow: 'shadow-lg',
        };
      case 'ocean-blue':
        return {
          baseClasses: 'p-3 rounded-2xl',
          defaultColors: 'bg-gradient-to-br from-blue-500 to-cyan-600 hover:from-blue-600 hover:to-cyan-700 text-white',
          toggledColors: 'bg-gradient-to-br from-blue-100 to-cyan-100 dark:from-gray-700 dark:to-gray-800 hover:from-blue-200 hover:to-cyan-200 dark:hover:from-gray-600 dark:hover:to-gray-700 text-blue-900 dark:text-white',
          shadow: 'shadow-lg',
        };
      case 'light-mode':
        return {
          baseClasses: 'p-3 rounded-2xl',
          defaultColors: 'bg-gradient-to-br from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 text-white',
          toggledColors: 'bg-gradient-to-br from-gray-100 to-gray-200 hover:from-gray-200 hover:to-gray-300 text-gray-900',
          shadow: 'shadow-lg',
        };
      case 'dark-mode':
      default:
        return {
          baseClasses: 'p-3 rounded-2xl',
          defaultColors: 'bg-gradient-to-br from-zinc-700 to-zinc-800 hover:from-zinc-600 hover:to-zinc-700 text-white',
          toggledColors: 'bg-gradient-to-br from-zinc-700 to-zinc-800 hover:from-zinc-600 hover:to-zinc-700 text-white',
          shadow: 'shadow-lg',
        };
    }
  };

  // Position classes
  const getPositionClasses = () => {
    if (customPosition) return customPosition;

    const horizontal = position === 'right' ? 'right-[2.5%]' : 'left-[2.5%]';

    let vertical = '';
    switch (verticalPosition) {
      case 'top':
        vertical = 'top-[10%]';
        break;
      case 'bottom':
        vertical = 'bottom-[10%]';
        break;
      case 'center':
      default:
        vertical = 'top-1/2 -translate-y-1/2';
        break;
    }

    return `${horizontal} ${vertical}`;
  };

  const styles = getDesignStyles();
  const colorClasses = isToggled ? styles.toggledColors : styles.defaultColors;
  const CurrentIcon = isToggled && ToggledIcon ? ToggledIcon : Icon;
  const currentAriaLabel = isToggled && toggledAriaLabel ? toggledAriaLabel : ariaLabel;

  return (
    <button
      onClick={onClick}
      style={showInitialBounce ? { animation: 'fab-pulsate 1s ease-in-out' } : undefined}
      className={`
        fixed z-50
        transition-all duration-300
        ${getPositionClasses()}
        ${styles.baseClasses}
        ${colorClasses}
        ${styles.shadow}
        ${hasNotification && !isToggled ? 'animate-pulse' : ''}
        ${className}
      `}
      aria-label={currentAriaLabel}
    >
      <style jsx>{`
        @keyframes fab-pulsate {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.15); }
        }
      `}</style>
      {hasNotification && !isToggled && (
        <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full border-2 border-white shadow-md animate-pulse" />
      )}

      <CurrentIcon className="w-8 h-8 stroke-[1.5]" />
    </button>
  );
}
