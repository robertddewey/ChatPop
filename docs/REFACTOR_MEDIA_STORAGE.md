# MediaStorage Refactoring Plan

## Objective

Move `chats/utils/media/` to project-level utilities (`chatpop/utils/media/`) to make `MediaStorage` available across all Django apps.

## Motivation

- `MediaStorage` is a **project-wide utility**, not chat-specific
- Currently used by `chats` app (voice messages)
- Will be used by `photo_analysis` app (image uploads)
- Following Django best practices: app-specific code in apps, shared code in project namespace

## Scope

### Files to Move

```
FROM: backend/chats/utils/media/
  - __init__.py
  - storage.py
  - audio.py

TO: backend/chatpop/utils/media/
  - __init__.py
  - storage.py
  - audio.py
```

### Files to Update

**Only 1 file imports from the old location:**
- `backend/chats/tests/tests_voice_messages.py`

Change:
```python
from chats.utils.media import save_voice_message
```

To:
```python
from chatpop.utils.media import save_voice_message
```

## Implementation Steps

### 1. Create New Directory Structure

```bash
mkdir -p backend/chatpop/utils/media
```

### 2. Move Files

```bash
# Copy files to new location
cp backend/chats/utils/media/__init__.py backend/chatpop/utils/media/
cp backend/chats/utils/media/storage.py backend/chatpop/utils/media/
cp backend/chats/utils/media/audio.py backend/chatpop/utils/media/

# Create empty __init__.py for chatpop/utils/
touch backend/chatpop/utils/__init__.py
```

### 3. Update Import in Test File

```python
# backend/chats/tests/tests_voice_messages.py
# Line 6 (or wherever the import is)

# OLD:
from chats.utils.media import save_voice_message, get_voice_message_url, delete_voice_message

# NEW:
from chatpop.utils.media import save_voice_message, get_voice_message_url, delete_voice_message
```

### 4. Remove Old Files (Git Move)

```bash
# Use git mv to preserve history
git mv backend/chats/utils/media/__init__.py backend/chatpop/utils/media/__init__.py
git mv backend/chats/utils/media/storage.py backend/chatpop/utils/media/storage.py
git mv backend/chats/utils/media/audio.py backend/chatpop/utils/media/audio.py

# Clean up empty directory
rmdir backend/chats/utils/media/
```

## Verification

### Run Tests

```bash
cd backend
./venv/bin/python manage.py test chats.tests.tests_voice_messages -v 2
```

Expected: All tests pass without errors.

### Check Imports

```bash
# Verify no files still import from old location
grep -r "from chats.utils.media" backend/
grep -r "import chats.utils.media" backend/
```

Expected: No matches found (or only historical references in comments).

### Start Django Server

```bash
cd backend
ALLOWED_HOSTS=localhost,127.0.0.1,10.0.0.135 \
CORS_ALLOWED_ORIGINS="http://localhost:4000,https://localhost:4000" \
./venv/bin/daphne -e ssl:9000:privateKey=../certs/localhost+3-key.pem:certKey=../certs/localhost+3.pem \
-b 0.0.0.0 chatpop.asgi:application
```

Expected: Server starts without import errors.

## New Import Path

**Going forward, all apps should use:**
```python
from chatpop.utils.media import MediaStorage, save_voice_message, get_voice_message_url
```

**Example usage in new photo_analysis app:**
```python
from chatpop.utils.media import MediaStorage

def save_uploaded_photo(image_file):
    storage_path, storage_type = MediaStorage.save_file(
        file_obj=image_file,
        directory='photo_analysis',
        filename=f"{uuid.uuid4()}.jpg"
    )
    return storage_path, storage_type
```

## Rollback Plan

If issues arise:

```bash
# Revert git commits
git revert HEAD

# Or manually restore
git checkout HEAD~1 -- backend/chats/utils/media/
git checkout HEAD~1 -- backend/chatpop/utils/
git checkout HEAD~1 -- backend/chats/tests/tests_voice_messages.py
```

## Success Criteria

- ✅ All tests pass
- ✅ Django server starts without errors
- ✅ Voice message uploads still work
- ✅ No imports from old `chats.utils.media` location
- ✅ Git history preserved via `git mv`

## Future Imports

**photo_analysis app** will use:
```python
from chatpop.utils.media import MediaStorage
```

**Any new apps** needing media storage will use:
```python
from chatpop.utils.media import MediaStorage
```

## Estimated Time

**15-20 minutes** (includes testing)

---

**Status**: Ready to execute
**Last Updated**: 2025-10-22
