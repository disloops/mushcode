#!/bin/bash

# MUSH GPT Service Management Script
# Handles deployment, starting, stopping, and monitoring of the MUSH GPT API server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "This script should not be run as root"
        exit 1
    fi
}

# Check if systemd is available
check_systemd() {
    if ! command -v systemctl &> /dev/null; then
        log_error "systemd is not available on this system"
        exit 1
    fi
}

# Check if required files exist
check_config() {
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [[ ! -f "$script_dir/mush_gpt.py" ]]; then
        log_error "mush_gpt.py not found in $script_dir"
        exit 1
    fi

    if [[ ! -f "$script_dir/mush_gpt.env" ]]; then
        log_warning "mush_gpt.env not found. Creating from example..."
        if [[ -f "$script_dir/mush_gpt.env.example" ]]; then
            cp "$script_dir/mush_gpt.env.example" "$script_dir/mush_gpt.env"
            log_success "Created mush_gpt.env from example. Please edit it with your settings."
        else
            log_error "mush_gpt.env.example not found. Please create mush_gpt.env manually."
            exit 1
        fi
    fi
}

# Check Python dependencies
check_dependencies() {
    log_info "Checking Python dependencies..."

    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi

    # Check for required Python packages
    local missing_packages=()

    if ! python3 -c "import flask" 2>/dev/null; then
        missing_packages+=("flask")
    fi

    if ! python3 -c "import openai" 2>/dev/null; then
        missing_packages+=("openai")
    fi

    if [[ ${#missing_packages[@]} -gt 0 ]]; then
        log_error "Missing Python packages: ${missing_packages[*]}"
        log_info "Install them with: pip3 install ${missing_packages[*]}"
        exit 1
    fi

    log_success "All dependencies are available"
}

# Test configuration
test_config() {
    log_info "Testing configuration..."

    # Test if the script can start (without actually starting the server)
    if python3 -c "import sys; sys.path.append('.'); from mush_gpt import app; print('Configuration test passed')" 2>/dev/null; then
        log_success "Configuration test passed"
    else
        log_error "Configuration test failed. Check your mush_gpt.env file."
        exit 1
    fi
}

# Deploy the service
deploy_service() {
    log_info "Deploying MUSH GPT service..."

    # Check if already deployed
    if systemctl is-enabled mush_gpt &> /dev/null; then
        log_warning "Service is already deployed. Do you want to redeploy? (y/N)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log_info "Deployment cancelled"
            return
        fi
    fi

    # Get current user and working directory
    CURRENT_USER=$(whoami)
    WORKING_DIR=$(pwd)

    log_info "Configuring service for user: $CURRENT_USER"
    log_info "Working directory: $WORKING_DIR"

    # Create service file with proper paths
    sed "s|YOUR_USERNAME|$CURRENT_USER|g; s|YOUR_WORKING_DIRECTORY|$WORKING_DIR|g" mush_gpt.service > /tmp/mush_gpt.service

    # Copy service file
    sudo cp /tmp/mush_gpt.service /etc/systemd/system/mush_gpt.service
    rm /tmp/mush_gpt.service

    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable mush_gpt

    log_success "MUSH GPT service deployed successfully"
}

# Start the service
start_service() {
    log_info "Starting MUSH GPT service..."
    sudo systemctl start mush_gpt
    log_success "MUSH GPT service started"
}

# Stop the service
stop_service() {
    log_info "Stopping MUSH GPT service..."
    sudo systemctl stop mush_gpt
    log_success "MUSH GPT service stopped"
}

# Disable the service (stop and prevent auto-start)
disable_service() {
    log_info "Disabling MUSH GPT service..."
    sudo systemctl stop mush_gpt
    sudo systemctl disable mush_gpt
    log_success "MUSH GPT service stopped and disabled"
    log_info "Use '$0 enable' to re-enable the service"
}

# Enable the service (allow auto-start)
enable_service() {
    log_info "Enabling MUSH GPT service..."
    sudo systemctl enable mush_gpt
    log_success "MUSH GPT service enabled"
    log_info "Use '$0 start-service' to start the service"
}

# Restart the service
restart_service() {
    log_info "Restarting MUSH GPT service..."
    sudo systemctl restart mush_gpt
    log_success "MUSH GPT service restarted"
}

# Show service status
show_status() {
    log_info "MUSH GPT service status:"
    sudo systemctl status mush_gpt --no-pager
}

# Show service logs
show_logs() {
    log_info "MUSH GPT service logs (last 50 lines):"
    sudo journalctl -u mush_gpt -n 50 --no-pager
}

# Show help
show_help() {
    echo "MUSH GPT Service Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy        - Deploy the service (requires sudo)"
    echo "  start-service - Start the service"
    echo "  stop          - Stop the service"
    echo "  disable       - Stop and disable the service (prevents auto-start)"
    echo "  enable        - Enable the service (allows auto-start)"
    echo "  restart       - Restart the service"
    echo "  status        - Show service status"
    echo "  logs          - Show service logs"
    echo "  start         - Start manually (for testing)"
    echo "  help          - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 deploy     # Deploy the service"
    echo "  $0 start      # Start manually for testing"
    echo "  $0 status     # Check if service is running"
}

# Manual start (for testing)
main() {
    log_info "Starting MUSH GPT manually..."
    python3 mush_gpt.py
}

# Main script logic
case "${1:-help}" in
    "deploy")
        check_root
        check_systemd
        check_config
        check_dependencies
        test_config
        deploy_service
        ;;
    "start-service")
        check_systemd
        start_service
        ;;
    "stop")
        check_systemd
        stop_service
        ;;
    "disable")
        check_systemd
        disable_service
        ;;
    "enable")
        check_systemd
        enable_service
        ;;
    "restart")
        check_systemd
        restart_service
        ;;
    "status")
        check_systemd
        show_status
        ;;
    "logs")
        check_systemd
        show_logs
        ;;
    "start")
        main # Manual start
        ;;
    "help"|"")
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
