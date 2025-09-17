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

# Check if already installed
check_installation() {
    if command -v golinks &> /dev/null; then
        if uv tool list 2>/dev/null | grep -q golinks; then
            echo_warning "golinks is already installed"
            return 0
        fi
    fi
    return 1
}

# Install uv if missing
install_uv() {
    if ! command -v uv &> /dev/null; then
        echo_info "Installing uv package manager..."
        curl -LsSf https://astral.sh/uv/install.sh | sh

        # Source shell config to get uv in PATH
        if [ -f "$HOME/.bashrc" ]; then
            source "$HOME/.bashrc"
        elif [ -f "$HOME/.zshrc" ]; then
            source "$HOME/.zshrc"
        fi

        # Add to current shell session
        export PATH="$HOME/.cargo/bin:$PATH"

        if ! command -v uv &> /dev/null; then
            echo_error "Failed to install uv. Please install manually."
            exit 1
        fi
        echo_success "uv installed successfully"
    else
        echo_info "uv is already installed"
    fi
}

# Install golinks tool
install_golinks() {
    echo_info "Installing golinks..."

    # Install from the current directory if we're in the repo
    if [ -f "pyproject.toml" ]; then
        uv tool install .
    else
        # Install from PyPI or git
        uv tool install golinks
    fi

    if [ $? -eq 0 ]; then
        echo_success "golinks installed successfully"
    else
        echo_error "Failed to install golinks"
        exit 1
    fi
}

# Create configuration directory and file
setup_config() {
    CONFIG_DIR="$HOME/.config/golinks"
    CONFIG_FILE="$CONFIG_DIR/config.json"

    echo_info "Setting up configuration..."

    # Create config directory
    mkdir -p "$CONFIG_DIR"

    # Create config file if it doesn't exist
    if [ ! -f "$CONFIG_FILE" ]; then
        cat > "$CONFIG_FILE" <<EOF
{
  "github": "https://github.com",
  "mail": "https://gmail.com",
  "calendar": "https://calendar.google.com",
  "docs": "https://docs.google.com",
  "drive": "https://drive.google.com",
  "repo": {
    "template_url": "https://github.com/{1}/{2}",
    "defaults": {
      "1": "haranrk",
      "2": "golinks"
    }
  }
}
EOF
        echo_success "Configuration file created at $CONFIG_FILE"
    else
        echo_info "Configuration file already exists"
    fi
}

# Add entry to /etc/hosts
setup_hosts() {
    echo_info "Configuring /etc/hosts..."

    # Check if entry already exists
    if grep -q "127.0.0.1[[:space:]]*go$" /etc/hosts 2>/dev/null; then
        echo_info "/etc/hosts already configured"
    else
        echo_info "Adding 'go' to /etc/hosts (requires sudo)..."
        echo "127.0.0.1   go" | sudo tee -a /etc/hosts > /dev/null
        echo_success "Added 'go' to /etc/hosts"
    fi
}

# Setup LaunchAgent
setup_launchagent() {
    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST_FILE="$PLIST_DIR/com.user.golinks.plist"

    echo_info "Setting up LaunchAgent..."

    # Create LaunchAgents directory if it doesn't exist
    mkdir -p "$PLIST_DIR"

    # Find golinks executable path
    GOLINKS_PATH=$(which golinks)
    if [ -z "$GOLINKS_PATH" ]; then
        echo_error "golinks command not found in PATH"
        exit 1
    fi

    # Create plist file
    cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.golinks</string>
    <key>ProgramArguments</key>
    <array>
        <string>$GOLINKS_PATH</string>
        <string>--port</string>
        <string>8080</string>
        <string>--config</string>
        <string>$HOME/.config/golinks/config.json</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/.config/golinks/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.config/golinks/stderr.log</string>
</dict>
</plist>
EOF

    echo_success "LaunchAgent plist created"
}

# Setup port forwarding (port 80 -> 8080)
setup_port_forwarding() {
    echo_info "Setting up port 80 forwarding to 8080..."

    # Check if pf anchor file already exists
    if [ -f "/etc/pf.anchors/golinks" ]; then
        echo_warning "Port forwarding anchor already exists"
    else
        echo_info "Creating port forwarding rule (requires sudo)..."

        # Create the anchor file
        echo "rdr pass on lo0 inet proto tcp from any to 127.0.0.1 port 80 -> 127.0.0.1 port 8080" | sudo tee /etc/pf.anchors/golinks > /dev/null

        echo_success "Port forwarding anchor created"
    fi

    # Check if pf.conf already includes our anchor
    if sudo grep -q "golinks" /etc/pf.conf 2>/dev/null; then
        echo_info "pf.conf already configured for golinks"
    else
        echo_info "Updating pf.conf (requires sudo)..."

        # Backup pf.conf
        sudo cp /etc/pf.conf /etc/pf.conf.backup.$(date +%Y%m%d%H%M%S)

        # Add rdr-anchor after other rdr-anchor lines (with proper newline)
        sudo sed -i '' '/^rdr-anchor "com.apple\/\*"/a\
rdr-anchor "golinks"
' /etc/pf.conf

        # Add load anchor after the com.apple load anchor (with proper newline)
        sudo sed -i '' '/^load anchor "com.apple" from "\/etc\/pf.anchors\/com.apple"/a\
load anchor "golinks" from "/etc/pf.anchors/golinks"
' /etc/pf.conf

        echo_success "pf.conf updated"
    fi

    # Enable pfctl
    echo_info "Enabling packet filtering..."
    sudo pfctl -e 2>/dev/null || true
    sudo pfctl -f /etc/pf.conf 2>/dev/null || {
        echo_warning "Could not reload pf.conf. You may need to restart or manually run: sudo pfctl -f /etc/pf.conf"
    }

    echo_success "Port forwarding setup complete (80 -> 8080)"
}

# Start the service
start_service() {
    PLIST_FILE="$HOME/Library/LaunchAgents/com.user.golinks.plist"

    echo_info "Starting golinks service..."

    # Unload if already loaded
    launchctl unload "$PLIST_FILE" 2>/dev/null || true

    # Load the service
    launchctl load "$PLIST_FILE"

    # Wait for service to start
    echo_info "Waiting for service to start..."
    sleep 3

    # Verify service is running
    if curl -s http://localhost:8080/ | grep -q "Go Links" 2>/dev/null; then
        echo_success "Service started successfully at http://localhost:8080"
    else
        echo_warning "Service may not be running. Check logs at ~/.config/golinks/"
    fi
}

# Main installation flow
main() {
    echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║      GoLinks Installation Script     ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
    echo ""

    # Check if already installed
    if check_installation; then
        read -p "golinks is already installed. Reinstall? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo_info "Installation cancelled"
            exit 0
        fi
    fi

    # Run installation steps
    install_uv
    install_golinks
    setup_config
    setup_hosts
    setup_launchagent
    setup_port_forwarding
    start_service

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Installation Complete! 🎉          ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
    echo ""
    echo "Usage examples:"
    echo "  • Visit http://go to see the configured links"
    echo "  • Use a link: open http://go/<slug>"
    echo ""
    echo "Logs are available at: ~/.config/golinks/"
}

# Run main function
main