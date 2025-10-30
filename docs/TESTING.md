# Testing Documentation

ChatPop uses pytest with Allure Framework for self-documenting tests and beautiful HTML reports.

## Philosophy: Self-Documenting Tests

**The primary value is making tests readable in code.** The decorators document tests inline, making them understandable without any tooling. The HTML reports are a bonus for stakeholders, not required for development.

## Installation (Developers)

**✅ Required for all developers:**
```bash
# Install Python package (2MB, already in requirements.txt)
./venv/bin/pip install allure-pytest
```

**❌ NOT required:**
- Allure CLI (400MB+ with Java dependencies)
- Local report viewing

## Running Tests with Allure

### Quick Start: Test Runner Script (Recommended)

```bash
# Run all tests
./run_tests.sh

# Run tests and generate HTML report
./run_tests.sh --open

# Run with coverage report
./run_tests.sh --coverage

# Run specific test file
./run_tests.sh chats/tests/tests_security.py

# See all options
./run_tests.sh --help
```

The test runner script (`run_tests.sh`) is a convenient wrapper around pytest with built-in support for:
- Allure report generation
- Code coverage reporting
- Clear, colorized output
- Docker-based report viewing (no CLI installation needed)

### Manual pytest Commands

```bash
# Run all tests and generate Allure results
./venv/bin/pytest chats/tests --alluredir=allure-results

# Run specific test file
./venv/bin/pytest chats/tests/tests_security.py --alluredir=allure-results
```

The `allure-results/` directory contains JSON files that can be converted to HTML reports via CI/CD or Docker.

## Viewing Reports

### Option 1: Local Viewing with Test Runner (Easiest)

The `run_tests.sh` script handles everything for you:

```bash
# Run tests and open report in browser
./run_tests.sh --open
```

This automatically:
- Runs all tests with Allure results
- Generates HTML report using Docker
- Opens the report in your browser

**Note:** Requires Allure Docker image (prompted during installation, or run `docker pull frankescobar/allure-docker-service`)

### Option 2: CI/CD (Recommended for Team)

Reports are automatically generated and published by GitHub Actions. No local setup needed.

**View published reports at:** `https://yourorg.github.io/chatpop/test-reports`

See "CI/CD Integration" section below for setup instructions.

### Option 3: Manual Docker Command (Advanced)

If you prefer manual control or need to customize:

```bash
# 1. Run tests first
./venv/bin/pytest chats/tests --alluredir=allure-results

# 2. Generate HTML report using Docker (with macOS workaround)
# Note: Volume mounts don't work correctly with this image on macOS
# Using docker cp workaround instead

docker run --name allure-temp \
  -v $(pwd)/allure-results:/app/allure-results:ro \
  frankescobar/allure-docker-service \
  allure generate /app/allure-results -o /app/allure-report --clean

# 3. Copy report from container to host
docker cp allure-temp:/app/allure-report ./allure-report

# 4. Clean up
docker rm allure-temp
mv allure-report/allure-report/* allure-report/ && rmdir allure-report/allure-report

# 5. Open the report
open allure-report/index.html
```

**Note:** The `run_tests.sh` script handles all of this automatically, including the macOS Docker volume mount workaround.

## Adding Allure Decorators to Tests

### Basic Example

```python
import allure

@allure.feature('Chat Security')
@allure.story('JWT Session Authentication')
class ChatSessionSecurityTests(TestCase):
    """Test suite for JWT session security"""

    @allure.title("Message send requires valid session token")
    @allure.description("""
    Security test to verify that sending messages without
    a session token is properly blocked.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    def test_message_send_requires_session_token(self):
        # Test implementation
        pass
```

### Available Decorators

#### Class/Module Level
- `@allure.feature('Feature Name')` - High-level feature grouping
- `@allure.story('Story Name')` - User story or sub-feature

#### Test Level
- `@allure.title('Test Title')` - Human-readable test name
- `@allure.description('Description')` - Detailed test explanation
- `@allure.severity(level)` - Test importance
  - `allure.severity_level.BLOCKER`
  - `allure.severity_level.CRITICAL`
  - `allure.severity_level.NORMAL`
  - `allure.severity_level.MINOR`
  - `allure.severity_level.TRIVIAL`
- `@allure.tag('tag1', 'tag2')` - Custom tags for filtering
- `@allure.link('url', name='Link Text')` - Link to docs/tickets
- `@allure.issue('TICKET-123')` - Link to issue tracker
- `@allure.testcase('TC-456')` - Link to test case

### Runtime Attachments

```python
import allure

def test_example():
    # Attach text
    allure.attach('Debug info', name='Debug Log', attachment_type=allure.attachment_type.TEXT)

    # Attach JSON
    allure.attach(json.dumps(data), name='Response', attachment_type=allure.attachment_type.JSON)

    # Attach screenshot (for browser tests)
    allure.attach.file('screenshot.png', attachment_type=allure.attachment_type.PNG)
```

### Steps

```python
@allure.step('Step description')
def perform_action():
    # Step implementation
    pass

# Or inline
with allure.step('Performing database query'):
    result = db.query(...)
```

## Report Features

The Allure report includes:

- **Overview Dashboard** - Test statistics, trends, execution time
- **Suites View** - Tests organized by feature/story hierarchy
- **Graphs** - Status breakdown, severity, duration
- **Timeline** - Parallel test execution visualization
- **Behaviors** - Tests grouped by feature and story
- **Packages** - Tests organized by Python module structure
- **Categories** - Customizable failure categorization
- **History** - Trend analysis across multiple runs

## CI/CD Integration (Recommended Approach)

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        cd backend
        python -m venv venv
        ./venv/bin/pip install -r requirements.txt

    - name: Run tests with Allure
      run: |
        cd backend
        ./venv/bin/pytest chats/tests --alluredir=allure-results

    - name: Generate Allure Report
      uses: simple-elly/allure-report-action@master
      if: always()
      with:
        allure_results: backend/allure-results
        allure_report: allure-report
        gh_pages: gh-pages
        allure_history: allure-history

    - name: Deploy to GitHub Pages
      uses: peaceiris/actions-gh-pages@v3
      if: always()
      with:
        github_token: ${{ secrets.GITHUB_TOKEN }}
        publish_dir: allure-report
        destination_dir: test-reports
```

**Result:** Reports automatically published to `https://yourorg.github.io/chatpop/test-reports` on every push.

**Benefits:**
- No local tooling required for developers
- Cross-platform (works for Windows/Mac/Linux developers)
- Always up-to-date documentation
- Historical trend tracking
- Shareable links for PMs and stakeholders

## Configuration

### pytest.ini
```ini
[pytest]
addopts = --alluredir=allure-results --clean-alluredir
```

### allure.properties (optional)
Create `allure-results/allure.properties`:
```properties
allure.results.directory=allure-results
allure.link.issue.pattern=https://github.com/yourorg/yourrepo/issues/{}
allure.link.tms.pattern=https://jira.yourorg.com/browse/{}
```

## Example: Complete Annotated Test

```python
import allure
from django.test import TestCase

@allure.feature('User Authentication')
@allure.story('Login Flow')
class LoginTests(TestCase):

    @allure.title("Successful login with valid credentials")
    @allure.description("""
    Test the happy path login flow:
    1. User provides valid email and password
    2. System authenticates user
    3. Session token is issued
    4. User is redirected to dashboard
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag('authentication', 'smoke')
    @allure.testcase('TC-AUTH-001')
    def test_successful_login(self):
        with allure.step('Submit login form with valid credentials'):
            response = self.client.post('/api/auth/login/', {
                'email': 'user@example.com',
                'password': 'SecurePass123'
            })

        with allure.step('Verify response status is 200 OK'):
            self.assertEqual(response.status_code, 200)

        with allure.step('Verify session token is present'):
            self.assertIn('token', response.json())

        # Attach response for debugging
        allure.attach(
            json.dumps(response.json(), indent=2),
            name='Login Response',
            attachment_type=allure.attachment_type.JSON
        )
```

## Recommended Workflow

1. **Add decorators incrementally** - Start with `@allure.feature()` and `@allure.story()` on test classes
2. **Use clear titles** - Replace technical test names with human-readable titles
3. **Document intent** - Use `@allure.description()` to explain *why* the test exists
4. **Mark severity** - Tag critical security/business tests as `CRITICAL` or `BLOCKER`
5. **Use steps** - Break complex tests into documented steps
6. **Attach context** - Add screenshots, API responses, logs for easier debugging

## Benefits

- **Self-documenting tests** - Documentation lives with the code
- **Beautiful reports** - Professional, shareable HTML reports
- **Better debugging** - See exactly what failed and why
- **Trend analysis** - Track test stability over time
- **Team visibility** - Non-technical stakeholders can understand test coverage
- **No separate docs to maintain** - Single source of truth

## Next Steps

1. Add `@allure.feature()` and `@allure.story()` to all test classes
2. Add `@allure.title()` to tests that need clearer names
3. Use `@allure.severity()` to prioritize critical tests
4. Run tests and generate your first report!
