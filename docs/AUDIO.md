# Audio Implementation (iOS Safari Compatible)

## Overview

ChatPop uses a proven audio playback approach that works reliably on iOS Safari, which has strict audio restrictions.

**IMPORTANT:** iOS Safari has unique audio playback restrictions. The current implementation uses HTML5 `<audio>` elements with dynamically generated WAV files, which is the only approach that works consistently on iOS.

---

## Current Implementation

- **Location:** `/frontend/src/lib/sounds.ts`
- **Method:** HTML5 `<audio>` elements with dynamically generated WAV files (base64 data URLs)
- **Initialization:** AudioContext unlocked during "Join Chat" button click in `JoinChatModal`

---

## Why This Approach?

1. **Web Audio API alone DOES NOT work on iOS Safari** - even with a "running" AudioContext, iOS silently blocks output
2. **HTML5 Audio elements work reliably** - iOS treats them differently than Web Audio API
3. **One-time unlock** - The initial join gesture unlocks audio for the entire session

---

## How to Add New Sounds

To add sounds for pins, tips, or other events:

```typescript
// 1. Create a sound generator function in sounds.ts
const generatePinChime = (): string => {
  // Generate WAV file with higher frequency notes for urgency
  const notes = [783.99, 987.77]; // G5, B5
  // Use same WAV generation pattern as generateSuccessChime()
};

// 2. Export a play function
export const playPinSound = async () => {
  const audio = new Audio();
  audio.src = generatePinChime();
  audio.volume = 0.7;
  await audio.play();
};

// 3. Call from event handlers (WebSocket, etc.)
if (message.type === 'message_pinned') {
  playPinSound(); // No user gesture needed - already unlocked!
}
```

---

## Implementation Rules

### DO NOT:
- ❌ Use Web Audio API oscillators directly (silent on iOS)
- ❌ Require additional user gestures for each sound
- ❌ Use external audio files (slower, requires network)

### DO:
- ✅ Use HTML5 Audio elements
- ✅ Generate WAV files programmatically as base64 data URLs
- ✅ Unlock audio during the join gesture
- ✅ Reuse the unlocked state for all future sounds

---

## Technical Details

### Audio Unlocking

iOS Safari requires a user gesture (tap/click) to unlock audio playback. ChatPop unlocks audio during the "Join Chat" button click:

**File:** `/frontend/src/components/JoinChatModal.tsx`

```typescript
const handleJoin = async () => {
  // Unlock audio on iOS by playing a silent audio element
  const audio = new Audio();
  audio.src = generateSuccessChime(); // Generates base64 WAV
  audio.volume = 0.5;
  await audio.play().catch(() => {}); // Ignore errors

  // Continue with join logic...
};
```

Once unlocked, all future `playSuccessSound()` calls work without additional gestures.

### WAV File Generation

**File:** `/frontend/src/lib/sounds.ts`

The `generateSuccessChime()` function creates a WAV file programmatically:

1. Defines audio parameters (sample rate, bit depth, channels)
2. Generates audio samples for specific musical notes
3. Creates WAV header with file metadata
4. Encodes as base64 data URL
5. Returns `data:audio/wav;base64,{encoded_data}`

This approach:
- Works offline (no network requests)
- Fast generation (<1ms)
- Small file sizes (~10KB per sound)
- Reliable on iOS Safari

### Sound Design

**Success Chime Notes:**
- C5 (523.25 Hz) - 150ms
- E5 (659.25 Hz) - 150ms
- G5 (783.99 Hz) - 200ms

**Future Sound Examples:**
- **Pin Chime:** Higher notes (G5, B5) for urgency
- **Tip Received:** Lower notes (C4, E4, G4) for warmth
- **Host Message:** Single mid-range note (A4) for attention

---

## Troubleshooting

### Audio Not Playing on iOS

**Symptom:** Sounds work on desktop but not iOS Safari

**Solution:**
1. Verify audio is unlocked during join button click
2. Check that `audio.play()` is called synchronously within the gesture handler
3. Test with volume up (iOS respects system volume and silent mode)

### Audio Delayed or Stuttering

**Symptom:** Sound plays but with noticeable delay

**Solution:**
1. Pre-generate WAV files during app initialization
2. Cache generated base64 URLs in memory
3. Reduce WAV file sample rate (44.1kHz → 22.05kHz)

### Audio Works First Time But Not Subsequent Times

**Symptom:** First sound plays, then audio stops working

**Solution:**
1. Create new `Audio()` instance for each playback
2. Don't reuse audio elements (iOS Safari limitation)
3. Remove `audio.pause()` and `audio.currentTime = 0` resets

---

## Testing Checklist

When implementing new sounds:

- [ ] Test on iOS Safari (primary target)
- [ ] Test on Chrome Mobile (Android)
- [ ] Test in silent mode (sounds should respect mute switch)
- [ ] Test with low volume (ensure not too loud)
- [ ] Test multiple sounds in quick succession
- [ ] Test after device sleep/wake cycle
- [ ] Test with page reload (audio should re-unlock on join)

---

## Browser Compatibility

| Browser | Support | Notes |
|---------|---------|-------|
| iOS Safari | ✅ Full | Requires user gesture unlock |
| Chrome Mobile (Android) | ✅ Full | Works after any user interaction |
| Firefox Mobile | ✅ Full | Similar to Chrome |
| Desktop Chrome | ✅ Full | No restrictions |
| Desktop Safari | ✅ Full | No restrictions |
| Desktop Firefox | ✅ Full | No restrictions |

---

## Related Files

- **Sound Generation:** `/frontend/src/lib/sounds.ts`
- **Audio Unlock:** `/frontend/src/components/JoinChatModal.tsx`
- **Sound Usage:** `/frontend/src/app/chat/[code]/page.tsx` (join success)

---

## Future Enhancements

Potential improvements:
- Add sound settings (volume control, enable/disable)
- Pre-load sound files on app initialization
- Add haptic feedback for mobile devices
- Create sound theme system (different sounds per chat theme)

---

**Last Updated:** 2025-01-10
