# Database Fixtures

This directory contains Django fixtures (JSON exports) for seeding the database.

## Files

### `seed_data.json` (12KB, 302 lines)
**Safe for version control - COMMIT THIS FILE**

Contains essential seed data needed for the app to function:
- Chat themes (2 themes)
- System configuration settings (constance)

Load this fixture after running migrations:
```bash
./venv/bin/python manage.py loaddata fixtures/seed_data.json
```

### `full_dev_data.json` (170KB, 6324 lines)
**Development data only - DO NOT COMMIT**

Contains complete development database snapshot including:
- 33 test users (with hashed passwords)
- 18 chat rooms
- 119 messages
- All relationships and test data

This is for quickly setting up a populated development environment.

Load this fixture after running migrations:
```bash
./venv/bin/python manage.py loaddata fixtures/full_dev_data.json
```

## Usage

### For New Developers (Clean Database)

After setting up the project and running migrations:

```bash
# Load only essential data (recommended)
./venv/bin/python manage.py loaddata fixtures/seed_data.json

# OR load full development data (includes test users and chats)
./venv/bin/python manage.py loaddata fixtures/full_dev_data.json
```

### Regenerating Fixtures

If you update themes or config settings:

```bash
# Export seed data
./venv/bin/python manage.py dumpdata chats.chattheme constance \
  --natural-foreign --natural-primary --indent 2 \
  --output fixtures/seed_data.json

# Export full development data
./venv/bin/python manage.py dumpdata \
  --natural-foreign --natural-primary --indent 2 \
  --exclude contenttypes --exclude auth.permission \
  --exclude sessions.session --exclude authtoken \
  --output fixtures/full_dev_data.json
```

## Notes

- Passwords in fixtures are already hashed (safe to share)
- Auth tokens are excluded from exports (regenerated on login)
- Session data is excluded (temporary)
- `seed_data.json` should be committed to Git
- `full_dev_data.json` should NOT be committed (add to .gitignore)
