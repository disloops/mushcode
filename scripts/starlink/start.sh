#!/bin/bash

# Starlink Bot Startup Script
# This script helps manage the Starlink bot

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if starlink.env exists
check_config() {
    if [ ! -f "starlink.env" ]; then
        log_error "Configuration file starlink.env not found!"
        log_info "Please copy starlink.env.example to starlink.env and configure it:"
        log_info "  cp starlink.env.example starlink.env"
        log_info "  nano starlink.env"
        exit 1
    fi
    log_info "Configuration file found"
}

# Check if required packages are installed
check_dependencies() {
    log_info "Checking dependencies..."

    if ! python3 -c "import requests" 2>/dev/null; then
        log_error "requests package not found. Install with: pip install requests"
        exit 1
    fi

    log_info "All dependencies found"
}

# Test configuration
test_config() {
    log_info "Testing configuration..."

    # Source the environment file and export variables
    set -a  # Automatically export all variables
    source starlink.env
    set +a  # Turn off automatic export

    # Check required variables are set (not empty)
    local missing=()

    [ -z "$MUSH_HOST" ] && missing+=("MUSH_HOST")
    [ -z "$MUSH_PORT" ] && missing+=("MUSH_PORT")
    [ -z "$BOT_NAME" ] && missing+=("BOT_NAME")
    [ -z "$BOT_PASSWORD" ] && missing+=("BOT_PASSWORD")
    [ -z "$API_AUTH_KEY" ] && missing+=("API_AUTH_KEY")
    [ -z "$CHARACTER_NAME" ] && missing+=("CHARACTER_NAME")

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing required configuration in starlink.env:"
        for var in "${missing[@]}"; do
            echo "  - $var"
        done
        exit 1
    fi

    log_info "Configuration looks good"
}

# Check if running as root
check_root() {
    if [ "$EUID" -eq 0 ]; then
        log_error "This script should not be run as root for security reasons"
        log_info "Please run as a regular user with sudo privileges"
        exit 1
    fi
}

# Check if systemd is available
check_systemd() {
    if ! command -v systemctl >/dev/null 2>&1; then
        log_error "systemctl not found. This script requires systemd"
        exit 1
    fi
}

# Deploy the service
deploy_service() {
    log_info "Deploying Starlink service..."

    # Check if already deployed
    if systemctl is-enabled starlink >/dev/null 2>&1; then
        log_warn "Starlink service is already deployed and enabled"
        read -p "Do you want to redeploy it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Service deployment cancelled"
            return 0
        fi
    fi

    # Get current user and working directory
    CURRENT_USER=$(whoami)
    WORKING_DIR=$(pwd)

    log_info "Configuring service for user: $CURRENT_USER"
    log_info "Working directory: $WORKING_DIR"

    # Create temporary service file with actual paths
    log_info "Creating service file with actual paths..."
    sed "s|YOUR_USERNAME|$CURRENT_USER|g; s|YOUR_WORKING_DIRECTORY|$WORKING_DIR|g" starlink.service > /tmp/starlink.service

    # Copy service file
    log_info "Installing service file..."
    sudo cp /tmp/starlink.service /etc/systemd/system/starlink.service
    rm /tmp/starlink.service

    # Reload systemd
    log_info "Reloading systemd daemon..."
    sudo systemctl daemon-reload

    # Enable service
    log_info "Enabling Starlink service..."
    sudo systemctl enable starlink

    log_info "Service deployed successfully!"
    log_info "Use '$0 start-service' to start the service"
    log_info "Use '$0 status' to check service status"
}

# Start the service
start_service() {
    log_info "Starting Starlink service..."

    if ! systemctl is-enabled starlink >/dev/null 2>&1; then
        log_error "Starlink service is not deployed"
        log_info "Run '$0 deploy' first to deploy the service"
        exit 1
    fi

    sudo systemctl start starlink
    log_info "Service started"
    log_info "Use '$0 status' to check service status"
    log_info "Use '$0 logs' to view service logs"
}

# Stop the service
stop_service() {
    log_info "Stopping Starlink service..."
    sudo systemctl stop starlink
    log_info "Service stopped"
}

# Disable the service (stop and prevent auto-start)
disable_service() {
    log_info "Disabling Starlink service..."
    sudo systemctl stop starlink
    sudo systemctl disable starlink
    log_info "Service stopped and disabled"
    log_info "Use '$0 enable' to re-enable the service"
}

# Enable the service (allow auto-start)
enable_service() {
    log_info "Enabling Starlink service..."
    sudo systemctl enable starlink
    log_info "Service enabled"
    log_info "Use '$0 start-service' to start the service"
}

# Restart the service
restart_service() {
    log_info "Restarting Starlink service..."
    sudo systemctl restart starlink
    log_info "Service restarted"
    log_info "Use '$0 status' to check service status"
}

# Show service status
show_status() {
    log_info "Starlink service status:"
    sudo systemctl status starlink --no-pager
}

# Show service logs
show_logs() {
    log_info "Showing Starlink service logs (press Ctrl+C to exit):"
    sudo journalctl -u starlink -f
}

# Start the bot manually (without service)
start_bot() {
    log_info "Starting Starlink bot manually..."
    set -a  # Automatically export all variables
    source starlink.env
    set +a  # Turn off automatic export
    python3 starlink.py
}

# Main function for manual bot start
main() {
    log_info "Starlink Bot Startup Script"

    check_config
    check_dependencies
    test_config
    start_bot
}

# Show help information
show_help() {
    echo "Starlink Bot Management Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  deploy   - Deploy the service to systemd (requires sudo)"
    echo "  start    - Start the service"
    echo "  stop     - Stop the service"
    echo "  restart  - Restart the service"
    echo "  status   - Show service status"
    echo "  logs     - Show service logs (follow mode)"
    echo "  enable   - Enable the service (allows auto-start)"
    echo "  disable  - Stop and disable the service (prevents auto-start)"
    echo "  run      - Run manually in foreground (for testing/debugging)"
    echo "  test     - Test configuration without starting"
    echo "  help     - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 deploy   # Deploy service (first time)"
    echo "  $0 start    # Start the service"
    echo "  $0 run      # Run manually for testing"
    echo "  $0 status   # Check if service is running"
}

# Handle command line arguments
case "${1:-help}" in
    "deploy")
        check_root
        check_systemd
        check_config
        check_dependencies
        test_config
        deploy_service
        ;;
    "start"|"start-service")
        check_systemd
        start_service
        ;;
    "stop")
        check_systemd
        stop_service
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
    "enable")
        check_systemd
        enable_service
        ;;
    "disable")
        check_systemd
        disable_service
        ;;
    "run")
        main
        ;;
    "test")
        check_config
        check_dependencies
        test_config
        log_info "Configuration test passed!"
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
