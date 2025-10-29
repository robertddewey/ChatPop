#!/bin/bash

#######################################
# ChatPop.app Installation Script
# Automated setup for macOS/Linux
#######################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Detect LAN IP address
detect_lan_ip() {
    local lan_ip=""

    # Try to detect LAN IP on macOS
    lan_ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)

    # Try Linux if macOS fails
    if [ -z "$lan_ip" ]; then
        lan_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi

    # Fall back to 127.0.0.1
    if [ -z "$lan_ip" ]; then
        lan_ip="127.0.0.1"
    fi

    echo "$lan_ip"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    local missing_deps=0

    # Check Python
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        print_success "Python $PYTHON_VERSION found"
    else
        print_error "Python 3.11+ is required but not found"
        missing_deps=1
    fi

    # Check Node.js
    if command_exists node; then
        NODE_VERSION=$(node --version)
        print_success "Node.js $NODE_VERSION found"
    else
        print_error "Node.js 18+ is required but not found"
        missing_deps=1
    fi

    # Check npm
    if command_exists npm; then
        NPM_VERSION=$(npm --version)
        print_success "npm $NPM_VERSION found"
    else
        print_error "npm is required but not found"
        missing_deps=1
    fi

    # Check Docker
    if command_exists docker; then
        print_success "Docker found"
    else
        print_error "Docker is required but not found"
        missing_deps=1
    fi

    # Check Docker Compose
    if command_exists docker-compose || docker compose version >/dev/null 2>&1; then
        print_success "Docker Compose found"
    else
        print_error "Docker Compose is required but not found"
        missing_deps=1
    fi

    # Check mkcert
    if command_exists mkcert; then
        print_success "mkcert found"
    else
        print_warning "mkcert not found - SSL certificates are required for voice messages"
        echo ""
        echo "Install mkcert:"
        echo "  macOS:  brew install mkcert && mkcert -install"
        echo "  Linux:  sudo apt install mkcert && mkcert -install  # Debian/Ubuntu"
        echo ""
        read -p "Do you want to continue without mkcert? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
        missing_deps=1
    fi

    if [ $missing_deps -eq 1 ]; then
        print_error "Some prerequisites are missing. Please install them and try again."
        exit 1
    fi

    print_success "All prerequisites satisfied"
}

# Generate SSL certificates
setup_ssl_certificates() {
    print_header "Setting Up SSL Certificates"

    if [ -d "certs" ] && [ -f "certs/localhost+3.pem" ] && [ -f "certs/localhost+3-key.pem" ]; then
        print_info "SSL certificates already exist"
        read -p "Regenerate certificates? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_success "Using existing certificates"
            return
        fi
    fi

    if ! command_exists mkcert; then
        print_error "mkcert is required to generate SSL certificates"
        exit 1
    fi

    # Detect LAN IP address
    LAN_IP=$(detect_lan_ip)
    print_info "Detected LAN IP: $LAN_IP"

    mkdir -p certs
    cd certs

    print_info "Generating SSL certificates with mkcert..."
    mkcert localhost 127.0.0.1 $LAN_IP ::1

    # Rename if needed (mkcert naming can vary)
    if [ ! -f "localhost+3.pem" ]; then
        # Find the generated cert file
        CERT_FILE=$(ls -t localhost*.pem 2>/dev/null | grep -v "key" | head -1)
        KEY_FILE=$(ls -t localhost*-key.pem 2>/dev/null | head -1)

        if [ -n "$CERT_FILE" ] && [ -n "$KEY_FILE" ]; then
            mv "$CERT_FILE" localhost+3.pem 2>/dev/null || true
            mv "$KEY_FILE" localhost+3-key.pem 2>/dev/null || true
        fi
    fi

    cd ..

    if [ -f "certs/localhost+3.pem" ] && [ -f "certs/localhost+3-key.pem" ]; then
        print_success "SSL certificates generated successfully"
    else
        print_error "Failed to generate SSL certificates"
        exit 1
    fi
}

# Start Docker containers
start_docker_containers() {
    print_header "Starting Docker Containers"

    print_info "Starting PostgreSQL and Redis containers..."
    docker-compose up -d

    # Wait for containers to be ready
    print_info "Waiting for containers to be ready..."
    sleep 10

    # Check if containers are running
    if docker ps --filter "name=chatpop" | grep -q chatpop; then
        print_success "Docker containers are running"
        docker ps --filter "name=chatpop" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        print_error "Failed to start Docker containers"
        exit 1
    fi
}

# Setup backend
setup_backend() {
    print_header "Setting Up Backend (Django)"

    cd backend

    # Create virtual environment
    if [ ! -d "venv" ]; then
        print_info "Creating Python virtual environment..."
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_info "Virtual environment already exists"
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Upgrade pip
    print_info "Upgrading pip..."
    pip install --upgrade pip --quiet

    # Install dependencies
    print_info "Installing Python dependencies (this may take a few minutes)..."
    pip install -r requirements.txt --quiet
    print_success "Python dependencies installed"

    # Create .env file
    if [ ! -f ".env" ]; then
        print_info "Creating backend .env file..."
        cp .env.example .env
        print_success "Backend .env file created"
    else
        print_info "Backend .env file already exists"
    fi

    # Run migrations
    print_info "Running database migrations..."
    ./venv/bin/python manage.py migrate
    print_success "Database migrations completed"

    # Load fixtures
    if [ -f "fixtures/seed_data.json" ]; then
        print_info "Loading seed data (chat themes, config settings)..."
        ./venv/bin/python manage.py loaddata fixtures/seed_data.json
        print_success "Seed data loaded"
    else
        print_warning "Seed data fixture not found (fixtures/seed_data.json)"
    fi

    # Optional: Load full development data
    echo ""
    read -p "Load full development data (test users, chats, messages)? May be stale (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -f "fixtures/full_dev_data.json" ]; then
            print_info "Loading full development data..."
            ./venv/bin/python manage.py loaddata fixtures/full_dev_data.json
            print_success "Full development data loaded"
        else
            print_warning "full_dev_data.json not found (fixtures/full_dev_data.json)"
        fi
    else
        print_info "Skipping full development data"
    fi

    # Deactivate virtual environment
    deactivate

    cd ..
    print_success "Backend setup completed"
}

# Setup frontend
setup_frontend() {
    print_header "Setting Up Frontend (Next.js)"

    cd frontend

    # Install dependencies
    print_info "Installing npm dependencies (this may take a few minutes)..."
    npm install --silent
    print_success "npm dependencies installed"

    # Create .env.local file
    if [ ! -f ".env.local" ]; then
        if [ -f ".env.example" ]; then
            print_info "Creating frontend .env.local file..."
            cp .env.example .env.local
            print_success "Frontend .env.local file created"
        else
            print_warning ".env.example not found, creating default .env.local..."
            cat > .env.local <<EOF
# Backend API URL (use https for SSL)
NEXT_PUBLIC_API_URL=https://localhost:9000

# WebSocket URL (use wss for secure websockets)
NEXT_PUBLIC_WS_URL=wss://localhost:9000

# Frontend server port (MUST be 4000 per project standards)
PORT=4000

# Stripe Publishable Key (test mode)
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key

# Environment (development, production)
NODE_ENV=development
EOF
            print_success "Default .env.local file created"
        fi
    else
        print_info "Frontend .env.local file already exists"
    fi

    cd ..
    print_success "Frontend setup completed"
}

# Print completion message
print_completion() {
    print_header "Installation Complete!"

    # Detect LAN IP for completion message
    LAN_IP=$(detect_lan_ip)

    echo -e "${GREEN}ChatPop.app is now installed and ready to use!${NC}\n"

    echo -e "${BLUE}Next Steps:${NC}"
    echo -e "1. Start the backend server (in a new terminal):"
    echo -e "   ${YELLOW}cd backend${NC}"
    echo -e "   ${YELLOW}ALLOWED_HOSTS=localhost,127.0.0.1,$LAN_IP \\${NC}"
    echo -e "   ${YELLOW}CORS_ALLOWED_ORIGINS=\"http://localhost:4000,https://localhost:4000,http://$LAN_IP:4000,https://$LAN_IP:4000\" \\${NC}"
    echo -e "   ${YELLOW}./venv/bin/daphne -e ssl:9000:privateKey=../certs/localhost+3-key.pem:certKey=../certs/localhost+3.pem -b 0.0.0.0 chatpop.asgi:application${NC}"
    echo ""
    echo -e "2. Start the frontend server (in another new terminal):"
    echo -e "   ${YELLOW}cd frontend${NC}"
    echo -e "   ${YELLOW}npm run dev:https${NC}"
    echo ""
    echo -e "${BLUE}Access the application:${NC}"
    echo -e "   Frontend:     ${GREEN}https://localhost:4000${NC}"
    echo -e "   Backend API:  ${GREEN}https://localhost:9000${NC}"
    echo -e "   Django Admin: ${GREEN}https://localhost:9000/admin${NC}"

    if [ "$LAN_IP" != "127.0.0.1" ]; then
        echo ""
        echo -e "${BLUE}Mobile/LAN Access (other devices on your network):${NC}"
        echo -e "   Frontend:     ${GREEN}https://$LAN_IP:4000${NC}"
        echo -e "   Backend API:  ${GREEN}https://$LAN_IP:9000${NC}"
    fi

    echo ""
    echo -e "${YELLOW}Note:${NC} You may see a browser security warning about the self-signed certificate."
    echo -e "      Click 'Advanced' → 'Proceed to localhost' to continue. This is safe for local development."
    echo ""
    echo -e "${BLUE}Optional:${NC} Create a Django superuser to access the admin panel:"
    echo -e "   ${YELLOW}cd backend${NC}"
    echo -e "   ${YELLOW}./venv/bin/python manage.py createsuperuser${NC}"
    echo ""
}

# Detect and clean previous installation
detect_previous_installation() {
    print_header "Checking for Previous Installation"

    local needs_cleanup=0
    local issues=()

    # Check for backend venv
    if [ -d "backend/venv" ]; then
        issues+=("Backend virtual environment (backend/venv)")
        needs_cleanup=1
    fi

    # Check for backend .env
    if [ -f "backend/.env" ]; then
        issues+=("Backend configuration file (backend/.env)")
        needs_cleanup=1
    fi

    # Check for frontend node_modules
    if [ -d "frontend/node_modules" ]; then
        issues+=("Frontend dependencies (frontend/node_modules)")
        needs_cleanup=1
    fi

    # Check for frontend .env.local
    if [ -f "frontend/.env.local" ]; then
        issues+=("Frontend configuration file (frontend/.env.local)")
        needs_cleanup=1
    fi

    # Check if Docker containers are running
    if docker ps --filter "name=chatpop" 2>/dev/null | grep -q chatpop; then
        issues+=("Running Docker containers")
        needs_cleanup=1
    fi

    # Check for Docker volumes (even if stopped)
    if docker volume ls 2>/dev/null | grep -q chatpop; then
        issues+=("Docker volumes with database data")
        needs_cleanup=1
    fi

    if [ $needs_cleanup -eq 0 ]; then
        print_success "No previous installation detected"
        return 0
    fi

    # Found previous installation
    print_warning "Detected previous installation artifacts:"
    for issue in "${issues[@]}"; do
        echo "  - $issue"
    done
    echo ""

    print_warning "A previous or partial installation may cause conflicts."
    echo ""
    echo -e "${YELLOW}Recommended: Clean up and start fresh${NC}"
    echo -e "${BLUE}This will:${NC}"
    echo "  1. Stop and remove Docker containers & volumes (database will be reset)"
    echo "  2. Remove backend virtual environment"
    echo "  3. Remove backend/frontend configuration files (.env, .env.local)"
    echo "  4. Keep: node_modules (will be reused), SSL certificates, source code"
    echo ""

    read -p "Clean up previous installation? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_info "Continuing with existing installation artifacts"
        print_warning "This may cause errors if the previous installation was incomplete"
        echo ""
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installation cancelled"
            exit 0
        fi
        return 0
    fi

    # Perform cleanup
    print_info "Cleaning up previous installation..."

    # Stop and remove Docker containers with volumes
    if docker ps --filter "name=chatpop" 2>/dev/null | grep -q chatpop; then
        print_info "Stopping Docker containers..."
        docker-compose down -v 2>/dev/null || true
    fi

    # Remove backend artifacts
    if [ -d "backend/venv" ]; then
        print_info "Removing backend virtual environment..."
        rm -rf backend/venv
    fi

    if [ -f "backend/.env" ]; then
        print_info "Removing backend .env file..."
        rm backend/.env
    fi

    # Remove frontend artifacts
    if [ -f "frontend/.env.local" ]; then
        print_info "Removing frontend .env.local file..."
        rm frontend/.env.local
    fi

    # Note: We keep node_modules and SSL certificates to save time

    print_success "Cleanup completed"
    echo ""
}

# Clone or update repository
setup_repository() {
    print_header "Repository Setup"

    # Check if we're already in a ChatPop directory
    if [ -f "docker-compose.yml" ] && [ -d "backend" ] && [ -d "frontend" ]; then
        print_info "Already in ChatPop directory"

        # Check if it's a git repository
        if [ -d ".git" ]; then
            # Show current branch
            CURRENT_BRANCH=$(git branch --show-current)
            print_info "Current branch: ${YELLOW}$CURRENT_BRANCH${NC}"

            # Ask if they want to switch branches
            echo ""
            read -p "Enter branch name (or press Enter to use current branch): " BRANCH

            if [ -n "$BRANCH" ]; then
                print_info "Switching to branch: $BRANCH"

                # Fetch latest branches
                print_info "Fetching latest branches..."
                git fetch origin

                # Check if branch exists remotely
                if git ls-remote --heads origin "$BRANCH" | grep -q "$BRANCH"; then
                    # Checkout the branch
                    git checkout "$BRANCH" || {
                        print_error "Failed to checkout branch $BRANCH"
                        exit 1
                    }

                    # Pull latest changes
                    print_info "Pulling latest changes..."
                    git pull origin "$BRANCH" || {
                        print_error "Failed to pull latest changes"
                        exit 1
                    }

                    print_success "Switched to branch $BRANCH and pulled latest changes"
                else
                    print_error "Branch $BRANCH does not exist remotely"
                    exit 1
                fi
            else
                # Pull latest changes for current branch
                print_info "Pulling latest changes for current branch..."
                git pull origin "$CURRENT_BRANCH" || {
                    print_warning "Could not pull latest changes (may not be a remote tracking branch)"
                }
                print_success "Using current branch: $CURRENT_BRANCH"
            fi
        else
            print_warning "Not a git repository - skipping repository update"
        fi

        return
    fi

    # Not in ChatPop directory - need to clone
    print_info "ChatPop repository not found in current directory"
    echo ""

    # Default repository URL
    DEFAULT_REPO="https://github.com/robertddewey/ChatPop.git"

    echo -e "${BLUE}Enter GitHub repository URL${NC}"
    echo -e "${YELLOW}(Press Enter for default: $DEFAULT_REPO)${NC}"
    read -p "Repository URL: " REPO_URL

    if [ -z "$REPO_URL" ]; then
        REPO_URL="$DEFAULT_REPO"
    fi

    # Ask for branch
    echo ""
    echo -e "${BLUE}Enter branch name${NC}"
    echo -e "${YELLOW}(Press Enter for default: main)${NC}"
    read -p "Branch: " BRANCH

    if [ -z "$BRANCH" ]; then
        BRANCH="main"
    fi

    # Ask where to clone
    echo ""
    echo -e "${BLUE}Enter directory name to clone into${NC}"
    echo -e "${YELLOW}(Press Enter for default: ChatPop)${NC}"
    read -p "Directory: " CLONE_DIR

    if [ -z "$CLONE_DIR" ]; then
        CLONE_DIR="ChatPop"
    fi

    # Check if directory already exists
    if [ -d "$CLONE_DIR" ]; then
        print_warning "Directory $CLONE_DIR already exists"

        # Check if it looks like a ChatPop directory
        if [ -f "$CLONE_DIR/docker-compose.yml" ] && [ -d "$CLONE_DIR/backend" ] && [ -d "$CLONE_DIR/frontend" ]; then
            print_info "Found existing ChatPop installation in $CLONE_DIR"
            echo ""
            read -p "Use this existing directory? (Y/n): " -n 1 -r
            echo

            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                # Change into existing directory
                cd "$CLONE_DIR" || {
                    print_error "Failed to change into directory $CLONE_DIR"
                    exit 1
                }

                print_success "Using existing directory: $CLONE_DIR"

                # Check if it's a git repo and offer to update
                if [ -d ".git" ]; then
                    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
                    print_info "Current branch: ${YELLOW}$CURRENT_BRANCH${NC}"

                    echo ""
                    read -p "Pull latest changes from remote? (Y/n): " -n 1 -r
                    echo

                    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                        print_info "Fetching latest changes..."
                        git fetch origin 2>/dev/null || print_warning "Could not fetch from remote"

                        print_info "Pulling latest changes..."
                        git pull 2>/dev/null || print_warning "Could not pull latest changes"

                        print_success "Repository updated"
                    else
                        print_info "Skipping repository update"
                    fi
                fi

                return 0
            else
                print_error "Please remove or rename the existing $CLONE_DIR directory and try again"
                exit 1
            fi
        else
            print_error "$CLONE_DIR exists but doesn't appear to be a ChatPop directory"
            print_info "Please remove or rename it and try again"
            exit 1
        fi
    fi

    # Clone the repository
    print_info "Cloning repository..."
    if git clone -b "$BRANCH" "$REPO_URL" "$CLONE_DIR"; then
        print_success "Repository cloned successfully"

        # Change into the directory
        cd "$CLONE_DIR" || {
            print_error "Failed to change into directory $CLONE_DIR"
            exit 1
        }

        print_success "Changed into directory: $CLONE_DIR"
    else
        print_error "Failed to clone repository"
        exit 1
    fi
}

# Main installation flow
main() {
    clear
    echo -e "${GREEN}"
    echo "  _____ _           _   ____             "
    echo " / ____| |         | | |  _ \\            "
    echo "| |    | |__   __ _| |_| |_) | ___  _ __ "
    echo "| |    | '_ \\ / _\` | __|  __/ / _ \\| '_ \\"
    echo "| |____| | | | (_| | |_| |   | (_) | |_) |"
    echo " \\_____|_| |_|\\__,_|\\__|_|    \\___/| .__/"
    echo "                                    | |   "
    echo "                                    |_|   "
    echo -e "${NC}"
    echo -e "${BLUE}Automated Installation Script for macOS/Linux${NC}\n"

    # Check if git is installed
    if ! command_exists git; then
        print_error "git is required but not found"
        echo ""
        echo "Install git:"
        echo "  macOS:  brew install git"
        echo "  Linux:  sudo apt install git  # Debian/Ubuntu"
        echo ""
        exit 1
    fi

    # Setup repository (clone or update)
    setup_repository

    # Verify we're now in the correct directory
    if [ ! -f "docker-compose.yml" ] || [ ! -d "backend" ] || [ ! -d "frontend" ]; then
        print_error "Not in ChatPop project root directory after repository setup"
        exit 1
    fi

    # Check for and clean previous installation artifacts
    detect_previous_installation

    # Confirm installation
    echo ""
    read -p "This will install ChatPop.app on your system. Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Installation cancelled"
        exit 0
    fi

    # Run installation steps
    check_prerequisites
    setup_ssl_certificates
    start_docker_containers
    setup_backend
    setup_frontend
    print_completion
}

# Run main function
main
