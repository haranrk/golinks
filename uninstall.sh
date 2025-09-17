#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Stop and remove LaunchAgent
remove_launchagent() {
    PLIST_FILE="$HOME/Library/LaunchAgents/com.user.golinks.plist"

    echo_info "Stopping golinks service..."

    if [ -f "$PLIST_FILE" ]; then
        # Unload the service
        launchctl unload "$PLIST_FILE" 2>/dev/null || {
            echo_warning "Service was not running"
        }

        # Remove plist file
        rm -f "$PLIST_FILE"
        echo_success "LaunchAgent removed"
    else
        echo_info "LaunchAgent not found"
    fi
}

# Uninstall golinks tool
uninstall_golinks() {
    echo_info "Uninstalling golinks tool..."

    if command -v golinks &> /dev/null; then
        if command -v uv &> /dev/null; then
            uv tool uninstall golinks 2>/dev/null || {
                echo_warning "golinks was not installed via uv"
            }
            echo_success "golinks uninstalled"
        else
            echo_warning "uv not found, cannot uninstall golinks tool"
        fi
    else
        echo_info "golinks not found in PATH"
    fi
}

# Remove port forwarding
remove_port_forwarding() {
    echo_info "Removing port 80 forwarding..."

    # Check if our anchor exists in pf.conf
    if sudo grep -q "golinks" /etc/pf.conf 2>/dev/null; then
        echo_info "Removing port forwarding from pf.conf (requires sudo)..."

        # Backup pf.conf
        sudo cp /etc/pf.conf /etc/pf.conf.backup.$(date +%Y%m%d%H%M%S)

        # Remove our anchor lines from pf.conf
        sudo sed -i '' '/^rdr-anchor "golinks"/d' /etc/pf.conf
        sudo sed -i '' '/^load anchor "golinks" from "\/etc\/pf.anchors\/golinks"/d' /etc/pf.conf

        echo_success "Removed port forwarding from pf.conf"

        # Reload pf.conf
        echo_info "Reloading packet filter configuration..."
        sudo pfctl -f /etc/pf.conf 2>/dev/null || {
            echo_warning "Could not reload pf.conf. You may need to restart"
        }
    else
        echo_info "No port forwarding configuration found in pf.conf"
    fi

    # Remove anchor file
    if [ -f "/etc/pf.anchors/golinks" ]; then
        echo_info "Removing port forwarding anchor file (requires sudo)..."
        sudo rm -f /etc/pf.anchors/golinks
        echo_success "Port forwarding anchor file removed"
    else
        echo_info "No port forwarding anchor file found"
    fi
}

# Remove entry from /etc/hosts
cleanup_hosts() {
    echo_info "Cleaning up /etc/hosts..."

    # Check if entry exists
    if grep -q "127.0.0.1[[:space:]]*go$" /etc/hosts 2>/dev/null; then
        echo_info "Removing 'go' from /etc/hosts (requires sudo)..."

        # Create backup
        sudo cp /etc/hosts /etc/hosts.backup.$(date +%Y%m%d%H%M%S)

        # Remove the line
        sudo sed -i '' '/^127\.0\.0\.1[[:space:]]*go$/d' /etc/hosts

        echo_success "Removed 'go' from /etc/hosts"
    else
        echo_info "No 'go' entry found in /etc/hosts"
    fi
}

# Remove configuration directory
remove_config() {
    CONFIG_DIR="$HOME/.config/golinks"

    if [ -d "$CONFIG_DIR" ]; then
        echo ""
        echo_warning "Configuration directory found at: $CONFIG_DIR"
        echo "This contains your links database and configuration."
        read -p "Remove configuration directory? (y/N): " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$CONFIG_DIR"
            echo_success "Configuration directory removed"
        else
            echo_info "Configuration directory preserved at: $CONFIG_DIR"
        fi
    else
        echo_info "No configuration directory found"
    fi
}

# Summary of what was removed
show_summary() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Uninstallation Summary             ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
    echo ""
    echo "The following components were processed:"
    echo "  ✓ LaunchAgent service stopped and removed"
    echo "  ✓ golinks tool uninstalled"
    echo "  ✓ Port 80 forwarding removed"
    echo "  ✓ /etc/hosts entry cleaned up"

    if [ ! -d "$HOME/.config/golinks" ]; then
        echo "  ✓ Configuration directory removed"
    else
        echo "  ℹ Configuration directory preserved"
    fi
}

# Main uninstallation flow
main() {
    echo -e "${YELLOW}╔══════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║    GoLinks Uninstallation Script    ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════╝${NC}"
    echo ""

    echo_warning "This will uninstall golinks from your system."
    read -p "Continue with uninstallation? (y/N): " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo_info "Uninstallation cancelled"
        exit 0
    fi

    # Run uninstallation steps
    remove_launchagent
    uninstall_golinks
    remove_port_forwarding
    cleanup_hosts
    remove_config

    show_summary

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Uninstallation Complete!           ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
    echo ""
    echo "golinks has been removed from your system."
}

# Run main function
main