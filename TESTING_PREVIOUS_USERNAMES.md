# Testing Previous Usernames Feature

## Overview

This document describes how to test the "previous usernames on rate limit" feature that was implemented for anonymous chat join flow.

## Feature Summary

When a user exhausts their 10 username generation attempts (by clicking the dice roll button), the system now returns their previously generated usernames (that are still available) so they can choose from them instead of being completely blocked.

## Implementation Details

**Backend Changes:**
- File: `/backend/chats/views.py` (lines 1025-1055)
- Endpoint: `POST /api/chats/{code}/suggest-username/`
- Enhancement: When returning 429 error (rate limited), also return `previous_usernames` array

**Frontend Changes:**
- File: `/frontend/src/components/JoinChatModal.tsx`
- UI: Grid display with clickable buttons for each previous username
- Behavior: Clicking a username populates the input field

## Manual Testing Steps

### Prerequisites

1. **Start Backend Server:**
   ```bash
   cd backend
   ALLOWED_HOSTS=localhost,127.0.0.1,10.0.0.135 \
   CORS_ALLOWED_ORIGINS="http://localhost:4000,http://127.0.0.1:4000,http://10.0.0.135:4000,https://localhost:4000,https://127.0.0.1:4000,https://10.0.0.135:4000" \
   ./venv/bin/daphne -e ssl:9000:privateKey=../certs/localhost+3-key.pem:certKey=../certs/localhost+3.pem -b 0.0.0.0 chatpop.asgi:application
   ```

2. **Start Frontend Server:**
   ```bash
   cd frontend
   npm run dev:https
   ```

3. **Access Application:**
   - Open browser to `https://localhost:4000`
   - Accept SSL certificate warning (self-signed cert)

### Test Procedure

#### Step 1: Create a Chat

1. Navigate to `https://localhost:4000`
2. Click "Create a ChatPop"
3. Fill in chat details (name, description, etc.)
4. Click "Create" to generate chat
5. **Copy the chat URL** (e.g., `https://localhost:4000/chat/ABC123`)

#### Step 2: Open Chat as Anonymous User

1. Open an **incognito/private browser window** (to ensure fresh fingerprint)
2. Paste the chat URL from Step 1
3. You should see the "Join Chat" modal

#### Step 3: Generate Usernames Until Rate Limited

1. In the "Join Chat" modal, look for the dice roll button (🎲) next to the username field
2. Click the dice button repeatedly to generate random usernames
3. **Count your clicks** - you should be able to generate 10 usernames
4. The counter below the button should show: "9 rolls remaining", "8 rolls remaining", etc.

#### Step 4: Observe the Rate Limit Behavior

1. After the 10th click, you should see:
   - Error message: "Max attempts reached. Choose from your previous usernames:"
   - A grid of buttons displaying your previously generated usernames (up to 10)
   - The buttons should be in a 2-column grid layout
   - Usernames should be alphabetically sorted
   - Usernames should be in TitleCase format (e.g., "HappyTiger42")

**Expected UI:**
```
┌──────────────────────────────────┐
│ Username: [____________]    🎲   │
│                                  │
│ ❌ Max attempts reached. Choose  │
│    from your previous usernames: │
│                                  │
│ ┌─────────────┬─────────────┐   │
│ │ BraveLion23 │ CoolCat456  │   │
│ ├─────────────┼─────────────┤   │
│ │ HappyTiger7 │ SmartDog890 │   │
│ ├─────────────┼─────────────┤   │
│ │ ...more...  │ ...more...  │   │
│ └─────────────┴─────────────┘   │
│                                  │
│ 0 rolls remaining                │
└──────────────────────────────────┘
```

#### Step 5: Select a Previous Username

1. Click on any of the displayed username buttons
2. **Verify:**
   - The username input field is populated with the clicked username
   - The previous usernames grid disappears
   - The error message is cleared
   - You can now submit the form to join the chat

#### Step 6: Join the Chat

1. With the selected username, click "Join Chat"
2. **Verify:**
   - You successfully join the chat
   - Your username appears in the participant list
   - You can send messages

### Advanced Test Cases

#### Test Case A: Username Availability

**Purpose:** Verify that taken usernames don't appear in previous usernames list

1. Open the chat in TWO different incognito windows (Window A and Window B)
2. In Window A: Generate 10 usernames and note the first one (e.g., "HappyTiger42")
3. In Window A: Select and join with "HappyTiger42"
4. In Window B: Generate 10 usernames
5. In Window B: Check the previous usernames list
6. **Verify:** "HappyTiger42" should NOT appear in Window B's list (it was taken by Window A)

#### Test Case B: Fingerprint Isolation

**Purpose:** Verify that different fingerprints have separate username history

1. Open the chat in an incognito window and generate 5 usernames
2. Note the generated usernames
3. Close the incognito window
4. Open a NEW incognito window (fresh fingerprint)
5. Navigate to the same chat
6. Generate usernames until rate limited
7. **Verify:** The previous usernames are DIFFERENT from the first session

#### Test Case C: TTL Expiration

**Purpose:** Verify that usernames expire after 60 minutes (default TTL)

1. Generate 10 usernames and hit rate limit
2. Note the displayed previous usernames
3. Wait 60 minutes (or adjust `USERNAME_RESERVATION_TTL_MINUTES` in Django Admin to 1 minute for faster testing)
4. Refresh the page
5. Generate 10 new usernames
6. **Verify:** The previous usernames from step 2 should NOT appear in the new list

### Constance Configuration

You can adjust the rate limit and TTL settings via Django Admin:

1. Navigate to `https://localhost:9000/admin/constance/config/`
2. Log in with admin credentials
3. Adjust these settings:
   - `MAX_ANONYMOUS_USERNAME_GENERATION_ATTEMPTS` (default: 10)
   - `USERNAME_RESERVATION_TTL_MINUTES` (default: 60 minutes)
4. Click "Save"
5. Settings take effect immediately (no server restart needed)

## API Response Format

When rate limited (429 error), the API returns:

```json
{
  "error": "Maximum username generation attempts exceeded.",
  "generation_remaining": 0,
  "previous_usernames": [
    "BraveLion23",
    "CoolCat456",
    "HappyTiger42",
    "SmartDog890"
  ]
}
```

## Files Changed

### Backend
- `/backend/chats/views.py:1025-1055` - Added `previous_usernames` to 429 response

### Frontend
- `/frontend/src/components/JoinChatModal.tsx:74` - Added `previousUsernames` state
- `/frontend/src/components/JoinChatModal.tsx:249-253` - Added username selection handler
- `/frontend/src/components/JoinChatModal.tsx:265-285` - Enhanced error handler
- `/frontend/src/components/JoinChatModal.tsx:422-438` - Added UI grid for previous usernames

## Success Criteria

- ✅ User can generate 10 random usernames
- ✅ After 10 attempts, user is shown their previous usernames
- ✅ Previous usernames are displayed in a 2-column grid
- ✅ Usernames are alphabetically sorted and in TitleCase
- ✅ Clicking a username populates the input field
- ✅ User can successfully join chat with selected username
- ✅ Taken usernames don't appear in previous list
- ✅ Different fingerprints have separate username history

## Troubleshooting

### Issue: No previous usernames appear

**Possible Causes:**
1. All generated usernames were taken by other users
2. Redis cache expired (TTL reached)
3. Redis is not running

**Resolution:**
- Check if Redis is running: `docker ps | grep redis`
- Verify username generation worked (check browser console for 200 responses)
- Try in a fresh incognito window

### Issue: Same usernames across different sessions

**Possible Causes:**
1. Browser fingerprint is being cached
2. Not using incognito mode

**Resolution:**
- Always use incognito/private mode for testing
- Try a different browser

### Issue: Rate limit not triggering

**Possible Causes:**
1. `MAX_ANONYMOUS_USERNAME_GENERATION_ATTEMPTS` is set too high
2. Redis cache was cleared between attempts

**Resolution:**
- Check Constance config in Django Admin
- Verify Redis is persistent between attempts

## Related Documentation

- [FEATURE_USERNAME_LIMITS.md](./docs/FEATURE_USERNAME_LIMITS.md) - Complete feature specification
- [ARCHITECTURE.md](./docs/ARCHITECTURE.md) - Global Username System architecture
- [TESTING.md](./docs/TESTING.md) - Full test suite documentation
