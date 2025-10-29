# Batch Photo Upload Configuration Files

This directory contains JSON configuration files for the `batch_photo_upload` management command.

## Available Configurations

### `all_photos.json`
Processes all 13 test images in the fixtures directory. Useful for comprehensive testing of the entire photo analysis pipeline.

**Usage:**
```bash
./venv/bin/python manage.py batch_photo_upload photo_analysis/tests/fixtures/all_photos.json
```

### `bourbon_vs_beer.json`
Tests the K-NN clustering fix for the "Bourbon vs Beer" problem. Uploads bourbon/whiskey photos first (to establish a cluster), then beer photos (to verify they properly separate or don't get washed out by the broader category). Total: 6 photos.

**Photo sequence:**
1. Jim Beam bourbon bottles (3 photos: Jim Beam bottle, Jim Beam bottles, whiskey bottle)
2. Beer/beverage photos (3 photos: Budweiser can, glass of beer, generic drink glass)

**Expected behavior:** With K-NN clustering (K=10), bourbon photos should create a tight cluster. When beer photos are uploaded, they should NOT be dominated by generic "Bar Room" suggestions, but instead maintain their own distinct clusters.

**Usage:**
```bash
./venv/bin/python manage.py batch_photo_upload photo_analysis/tests/fixtures/bourbon_vs_beer.json --no-cache
```

### `movie_posters.json`
Tests the "Twister vs Twisters" distinct entity preservation. The refinement system should recognize these as different movies (1996 vs 2024) and keep both suggestion sets distinct.

**Photo sequence:**
1. Twister (1996) movie poster
2. Twisters (2024) movie poster
3. Alternative Twisters poster
4. Star Wars: The Empire Strikes Back movie poster

**Expected behavior:** The refinement LLM should preserve distinct entities even when names are similar (Twister vs Twisters). Each movie should have separate suggestion clusters with proper noun restoration.

**Usage:**
```bash
./venv/bin/python manage.py batch_photo_upload photo_analysis/tests/fixtures/movie_posters.json --no-cache
```

### `labubu_test.json`
Tests 2 Labubu toy photos. Useful for testing how the system handles collectible toys and merchandising.

**Photo sequence:**
1. Single Labubu toy (test_labubu.png)
2. Multiple Labubu toys (test_multiple_labubu.png)

**Expected behavior:** Should generate suggestions related to collectible toys, merchandise, or fan communities.

**Usage:**
```bash
./venv/bin/python manage.py batch_photo_upload photo_analysis/tests/fixtures/labubu_test.json
```

### `beverages.json`
All 7 beverage-related photos (coffee, beer, bourbon, whiskey). Tests how the system handles a broad category with subcategories.

**Photo sequence:**
1. Coffee mug (1 photo)
2. Budweiser can (1 photo)
3. Glass of beer (1 photo)
4. Generic drink glass (1 photo)
5. Bourbon/whiskey photos (3 photos: Jim Beam bottle, Jim Beam bottles, whiskey bottle)

**Expected behavior:** Should create distinct clusters for coffee vs beer vs bourbon, not just generic "Beverage Chat" suggestions.

**Usage:**
```bash
./venv/bin/python manage.py batch_photo_upload photo_analysis/tests/fixtures/beverages.json --no-cache
```

## Command Options

All configurations support the following options:

- `--no-cache` - Force fresh API calls (clear cache for all photos)
- `--fingerprint=VALUE` - Set client fingerprint for rate limiting (default: `batch-test-fp`)
- `--delay=SECONDS` - Delay between uploads in seconds (default: 0)

## Example Workflows

### Test K-NN Clustering with Fresh Data
```bash
# Clear cache and upload bourbon photos first, then beer
./venv/bin/python manage.py batch_photo_upload photo_analysis/tests/fixtures/bourbon_vs_beer.json --no-cache --delay=1
```

### Test Refinement System
```bash
# Upload movie posters to test distinct entity preservation
./venv/bin/python manage.py batch_photo_upload photo_analysis/tests/fixtures/movie_posters.json --no-cache
```

### Full System Test
```bash
# Process all photos with 2-second delay between uploads
./venv/bin/python manage.py batch_photo_upload photo_analysis/tests/fixtures/all_photos.json --no-cache --delay=2
```

## Creating Custom Configurations

Create a JSON file with the following structure:

```json
{
  "photos": [
    "test_photo1.jpeg",
    "test_photo2.png",
    "test_photo3.jpeg"
  ]
}
```

**Important:** Photo filenames must exist in the `photo_analysis/tests/fixtures/` directory.
