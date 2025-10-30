#!/bin/bash

#######################################
# ChatPop Test Runner
# Wrapper for pytest with Allure reporting
#######################################

set -e  # Exit on error

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
GENERATE_REPORT=false
OPEN_REPORT=false
COVERAGE=false
PYTEST_ARGS=()

# Help message
show_help() {
    echo -e "${BLUE}ChatPop Test Runner${NC}"
    echo ""
    echo "Usage: ./run_tests.sh [OPTIONS] [PYTEST_ARGS]"
    echo ""
    echo -e "${YELLOW}Options:${NC}"
    echo "  --report         Generate Allure HTML report after tests"
    echo "  --open           Generate and open Allure HTML report"
    echo "  --coverage       Run tests with code coverage report"
    echo "  --help           Show this help message"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  ./run_tests.sh"
    echo "    Run all tests"
    echo ""
    echo "  ./run_tests.sh --report"
    echo "    Run tests and generate Allure HTML report"
    echo ""
    echo "  ./run_tests.sh --open"
    echo "    Run tests, generate report, and open in browser"
    echo ""
    echo "  ./run_tests.sh --coverage"
    echo "    Run tests with code coverage report"
    echo ""
    echo "  ./run_tests.sh chats/tests/tests_security.py"
    echo "    Run only security tests"
    echo ""
    echo "  ./run_tests.sh -v"
    echo "    Run tests in verbose mode"
    echo ""
    echo "  ./run_tests.sh -k test_message"
    echo "    Run only tests matching 'test_message'"
    echo ""
    echo "  ./run_tests.sh --report -v -k test_security"
    echo "    Run security tests verbosely and generate report"
    echo ""
    echo -e "${YELLOW}Common pytest flags:${NC}"
    echo "  -v, --verbose    Verbose output"
    echo "  -x, --exitfirst  Exit on first failure"
    echo "  -k EXPRESSION    Run tests matching expression"
    echo "  --lf             Run last failed tests"
    echo "  --ff             Run failed tests first"
    echo "  -s               Show print statements"
    echo ""
    echo -e "${BLUE}Test files:${NC}"
    echo "  chats/tests/tests_security.py       (17 tests) - JWT session security"
    echo "  chats/tests/tests_validators.py     (10 tests) - Username validation"
    echo "  chats/tests/tests_profanity.py      (26 tests) - Profanity filtering"
    echo "  chats/tests/tests_rate_limits.py    (12 tests) - Rate limiting"
    echo "  chats/tests/tests_dual_sessions.py  (16 tests) - Dual session management"
    echo "  chats/tests/tests_redis_cache.py    (49 tests) - Redis caching"
    echo ""
}

# Parse flags
while [[ $# -gt 0 ]]; do
    case $1 in
        --report)
            GENERATE_REPORT=true
            shift
            ;;
        --open)
            GENERATE_REPORT=true
            OPEN_REPORT=true
            shift
            ;;
        --coverage)
            COVERAGE=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${RED}✗${NC} Virtual environment not found (venv/)"
    echo "Run this from the backend/ directory after installation"
    exit 1
fi

# Check if Docker is available (needed for report generation)
if [ "$GENERATE_REPORT" = true ]; then
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗${NC} Docker not found"
        echo "Docker is required for report generation"
        echo "Run without --report flag or install Docker"
        exit 1
    fi

    # Check if Allure Docker image is available
    if ! docker images frankescobar/allure-docker-service | grep -q frankescobar; then
        echo -e "${YELLOW}⚠${NC} Allure Docker image not found"
        echo "Pulling frankescobar/allure-docker-service (~600MB)..."
        docker pull frankescobar/allure-docker-service
    fi
fi

# Print test configuration
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Running Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ ${#PYTEST_ARGS[@]} -eq 0 ]; then
    echo -e "${GREEN}Target:${NC} All tests (chats/tests/)"
else
    echo -e "${GREEN}Target:${NC} ${PYTEST_ARGS[@]}"
fi

echo -e "${GREEN}Coverage:${NC} $( [ "$COVERAGE" = true ] && echo "Enabled" || echo "Disabled" )"
echo -e "${GREEN}Report:${NC} $( [ "$GENERATE_REPORT" = true ] && echo "Will generate" || echo "Disabled" )"
echo ""

# Run tests with optional coverage
if [ "$COVERAGE" = true ]; then
    # Check if pytest-cov is installed
    if ! ./venv/bin/python -c "import pytest_cov" 2>/dev/null; then
        echo -e "${YELLOW}⚠${NC} pytest-cov not installed, installing..."
        ./venv/bin/pip install pytest-cov --quiet
    fi

    echo -e "${BLUE}Running tests with coverage...${NC}"
    ./venv/bin/pytest chats/tests --alluredir=allure-results --cov=chats --cov-report=html --cov-report=term "${PYTEST_ARGS[@]}"
    TEST_EXIT_CODE=$?

    if [ $TEST_EXIT_CODE -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓${NC} Coverage report generated: htmlcov/index.html"
    fi
else
    echo -e "${BLUE}Running tests...${NC}"
    ./venv/bin/pytest chats/tests --alluredir=allure-results "${PYTEST_ARGS[@]}"
    TEST_EXIT_CODE=$?
fi

echo ""

# Generate report if requested and tests passed
if [ "$GENERATE_REPORT" = true ]; then
    if [ $TEST_EXIT_CODE -eq 0 ]; then
        echo -e "${BLUE}Generating Allure HTML report...${NC}"

        # Remove old report
        rm -rf allure-report

        # Generate report using Docker with docker cp workaround (volume mounts don't work on macOS)
        CONTAINER_NAME="allure-temp-$$"
        docker run --name "$CONTAINER_NAME" \
          -v "$(pwd)/allure-results:/app/allure-results:ro" \
          frankescobar/allure-docker-service \
          allure generate /app/allure-results -o /app/allure-report --clean 2>/dev/null

        # Copy report from container to host
        docker cp "$CONTAINER_NAME:/app/allure-report" ./allure-report > /dev/null 2>&1

        # Remove temporary container
        docker rm "$CONTAINER_NAME" > /dev/null 2>&1

        # Fix nested directory if it exists (docker cp behavior)
        if [ -d "allure-report/allure-report" ]; then
            mv allure-report/allure-report/* allure-report/ 2>/dev/null
            rmdir allure-report/allure-report 2>/dev/null
        fi

        echo -e "${GREEN}✓${NC} Report generated: allure-report/index.html"

        if [ "$OPEN_REPORT" = true ]; then
            echo -e "${BLUE}Starting HTTP server for report...${NC}"

            # Find an available port
            PORT=8765
            while lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; do
                PORT=$((PORT + 1))
            done

            echo ""
            echo -e "${GREEN}Report available at:${NC} http://localhost:$PORT"
            echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
            echo ""

            # Open browser after short delay
            (sleep 1 && \
                if command -v open &> /dev/null; then
                    open "http://localhost:$PORT"
                elif command -v xdg-open &> /dev/null; then
                    xdg-open "http://localhost:$PORT"
                fi
            ) &

            # Start HTTP server in allure-report directory
            cd allure-report && python3 -m http.server $PORT --bind 127.0.0.1 2>/dev/null
            cd ..
        fi
    else
        echo -e "${YELLOW}⚠${NC} Skipping report generation due to test failures"
        echo "Fix failing tests and run with --report to generate report"
    fi
fi

# Print summary
echo ""
echo -e "${BLUE}========================================${NC}"
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo -e "${RED}✗ Some tests failed${NC}"
fi
echo -e "${BLUE}========================================${NC}"

exit $TEST_EXIT_CODE
