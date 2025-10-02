import { useCallback, useRef, useState } from 'react';

interface UseLongPressOptions {
  onLongPress: () => void;
  onClick?: () => void;
  onTouchStart?: () => void; // Called immediately on touch start
  threshold?: number; // ms to hold before triggering
  cancelOnMove?: boolean; // cancel if finger/mouse moves
}

export function useLongPress({
  onLongPress,
  onClick,
  onTouchStart,
  threshold = 500,
  cancelOnMove = true,
}: UseLongPressOptions) {
  const [longPressTriggered, setLongPressTriggered] = useState(false);
  const timeout = useRef<NodeJS.Timeout>();
  const target = useRef<EventTarget>();
  const startPos = useRef<{ x: number; y: number }>();

  const start = useCallback(
    (event: React.MouseEvent | React.TouchEvent) => {
      // Call onTouchStart immediately during the user gesture
      if (onTouchStart) {
        onTouchStart();
      }

      // Store start position
      if ('touches' in event) {
        startPos.current = {
          x: event.touches[0].clientX,
          y: event.touches[0].clientY,
        };
      } else {
        startPos.current = {
          x: event.clientX,
          y: event.clientY,
        };
      }

      target.current = event.target;
      timeout.current = setTimeout(() => {
        onLongPress();
        setLongPressTriggered(true);
      }, threshold);
    },
    [onLongPress, onTouchStart, threshold]
  );

  const clear = useCallback(
    (event: React.MouseEvent | React.TouchEvent, shouldTriggerClick = true) => {
      timeout.current && clearTimeout(timeout.current);

      if (shouldTriggerClick && !longPressTriggered && onClick) {
        onClick();
      }

      setLongPressTriggered(false);
      target.current = undefined;
      startPos.current = undefined;
    },
    [onClick, longPressTriggered]
  );

  const move = useCallback(
    (event: React.MouseEvent | React.TouchEvent) => {
      if (!cancelOnMove || !startPos.current) return;

      let currentX: number, currentY: number;

      if ('touches' in event) {
        currentX = event.touches[0].clientX;
        currentY = event.touches[0].clientY;
      } else {
        currentX = event.clientX;
        currentY = event.clientY;
      }

      const moveThreshold = 10; // pixels
      const deltaX = Math.abs(currentX - startPos.current.x);
      const deltaY = Math.abs(currentY - startPos.current.y);

      if (deltaX > moveThreshold || deltaY > moveThreshold) {
        timeout.current && clearTimeout(timeout.current);
      }
    },
    [cancelOnMove]
  );

  return {
    onMouseDown: start,
    onMouseUp: clear,
    onMouseLeave: (e: React.MouseEvent) => clear(e, false),
    onTouchStart: start,
    onTouchEnd: clear,
    onMouseMove: move,
    onTouchMove: move,
  };
}
