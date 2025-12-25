#!/usr/bin/env python3
"""Go Links redirect server."""

import argparse
import json
import re
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError

from src.models import GoLinksConfig, LinkTemplate

PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.user.golinks.plist"
CONFIG_DIR = Path.home() / ".config" / "golinks"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.json"


class GoLinksHandler(BaseHTTPRequestHandler):
    """HTTP request handler for go links."""

    def __init__(self, *args, config_path: Path = Path.home() / ".golinks" / "config.json", **kwargs):
        self.config_path = config_path
        # Set up Jinja2 template environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
        super().__init__(*args, **kwargs)

    def get_config_path_display(self) -> str:
        """Get the config path as a string for display."""
        return str(self.config_path.absolute())
        # try:
        #     if self.config_path is None:
        #         return "Not configured"
        #     # Use absolute() instead of resolve() - resolve() can fail if file doesn't exist
        #     return str(Path(self.config_path).absolute())
        # except Exception:
        #     return str(self.config_path) if self.config_path else "Unknown"

    @property
    def config(self):
        """Load configuration from JSON file."""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Config file not found: {self.config_path}")

            with open(self.config_path, "r") as f:
                config_data = json.load(f)

            # Parse with Pydantic model
            config_model = GoLinksConfig(config_data)
            return config_model.root
        except json.JSONDecodeError as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            raise e
        except Exception as e:
            print(f"Unexpected error loading config: {e}", file=sys.stderr)
            raise e

    def do_GET(self):
        """Handle GET requests."""
        # Try to load config first
        try:
            config = self.config
        except (json.JSONDecodeError, FileNotFoundError, ValidationError) as e:
            self.show_config_error_page(e)
            return

        # Parse the path
        parsed = urlparse(self.path)
        path = parsed.path.strip("/")
        query = parsed.query

        # Root path - show all available links
        if not path:
            self.show_links_page(config)
            return

        # Split path into segments
        path_segments = path.split("/")
        shortcut = path_segments[0]
        remaining_segments = path_segments[1:] if len(path_segments) > 1 else []

        # Check if shortcut exists
        if shortcut in config:
            config_entry = config[shortcut]

            # Handle string config (backward compatible)
            if isinstance(config_entry, str):
                destination = config_entry
            # Handle LinkTemplate config
            elif isinstance(config_entry, LinkTemplate):
                template = config_entry.template_url
                defaults = config_entry.defaults

                # Check if template has placeholders
                if re.search(r"\{\d+\}", template):
                    destination = self.resolve_placeholders(
                        template, remaining_segments, defaults
                    )
                else:
                    destination = template
            else:
                self.show_error_page(path)
                return

            # Preserve query parameters
            if query:
                separator = "&" if "?" in destination else "?"
                destination = f"{destination}{separator}{query}"

            # Perform 301 redirect
            self.send_response(301)
            self.send_header("Location", destination)
            self.end_headers()
        else:
            # Show error page
            self.show_error_page(path, config)

    def show_links_page(self, config):
        """Display all available links."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        template = self.jinja_env.get_template("links.html")
        html = template.render(config=config, config_path=self.get_config_path_display())
        self.wfile.write(html.encode())

    def resolve_placeholders(
        self, template: str, segments: list, defaults: Dict[str, str]
    ) -> str:
        """Resolve placeholders in URL template."""
        # Find all placeholders using regex
        placeholders = re.findall(r"\{(\d+)\}", template)
        result = template

        for placeholder in placeholders:
            placeholder_num = placeholder
            placeholder_index = int(placeholder) - 1  # Convert to 0-based index

            # Determine the value to use
            if placeholder_index < len(segments) and segments[placeholder_index]:
                # Use provided segment
                value = segments[placeholder_index]
            elif placeholder_num in defaults:
                # Use default value
                value = defaults[placeholder_num]
            else:
                # No value available - use empty string as default
                value = ""

            # Replace the placeholder
            result = result.replace(f"{{{placeholder_num}}}", value)

        return result

    def show_error_page(self, path, config):
        """Display error page for unknown shortcuts."""
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        # Prepare suggestions
        suggestions = sorted(config.keys())[:10] if config else []
        remaining_count = (
            len(config) - 10 if config and len(config) > 10 else 0
        )

        template = self.jinja_env.get_template("error.html")
        html = template.render(
            path=path,
            config=config,
            suggestions=suggestions,
            remaining_count=remaining_count,
        )
        self.wfile.write(html.encode())

    def show_config_error_page(self, error: Exception):
        """Display error page for configuration errors."""
        self.send_response(500)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        # Determine error type and message
        if isinstance(error, json.JSONDecodeError):
            error_type = "JSON Syntax Error"
            error_message = f"Line {error.lineno}, Column {error.colno}: {error.msg}"
        elif isinstance(error, FileNotFoundError):
            error_type = "Configuration File Not Found"
            error_message = str(error)
        elif isinstance(error, ValidationError):
            error_type = "Configuration Validation Error"
            error_message = str(error)
        else:
            error_type = "Configuration Error"
            error_message = str(error)

        template = self.jinja_env.get_template("config_error.html")
        html = template.render(
            error_type=error_type,
            error_message=error_message,
            config_path=self.get_config_path_display(),
        )
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        """Override to customize logging."""
        # Only log actual redirects and errors, not successful page loads
        if args[1] in ["301", "404"]:
            sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


def run_server(host="127.0.0.1", port=8888, config_path=None):
    """Run the go links server."""

    # Create handler class with config path
    def handler_class(*args, **kwargs):
        return GoLinksHandler(*args, config_path=config_path, **kwargs)

    # Create and start server
    server = HTTPServer((host, port), handler_class)
    print(f"Go Links server running on http://{host}:{port}")
    print(
        f"Configuration file: {config_path or (Path.home() / '.golinks' / 'config.json')}"
    )
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()


def get_config_path(config_arg: Path | None) -> Path:
    """Resolve the config path from argument or defaults."""
    if config_arg:
        return config_arg

    # Use config in project directory if it exists
    local_config = Path(__file__).parent.parent.parent / "config.json"
    if local_config.exists():
        return local_config

    return DEFAULT_CONFIG_PATH


def ensure_config_exists(config_path: Path) -> None:
    """Ensure config directory and file exist."""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if not config_path.exists():
        default_config = {
            "github": "https://github.com",
            "mail": "https://gmail.com",
            "calendar": "https://calendar.google.com",
        }
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=2)
        print(f"Created default configuration at {config_path}")


def cmd_run_server(args: argparse.Namespace) -> None:
    """Handle run-server subcommand."""
    config_path = get_config_path(args.config)
    ensure_config_exists(config_path)
    run_server(args.host, args.port, config_path)


def setup_launchagent(golinks_path: str, port: int, config_path: Path) -> None:
    """Create LaunchAgent plist file."""
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.golinks</string>
    <key>ProgramArguments</key>
    <array>
        <string>{golinks_path}</string>
        <string>run-server</string>
        <string>--port</string>
        <string>{port}</string>
        <string>--config</string>
        <string>{config_path}</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{CONFIG_DIR}/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{CONFIG_DIR}/stderr.log</string>
</dict>
</plist>
"""
    PLIST_PATH.write_text(plist_content)
    print(f"LaunchAgent plist created at {PLIST_PATH}")


def cmd_start_service(args: argparse.Namespace) -> None:
    """Handle start-service subcommand."""
    # Find golinks executable
    golinks_path = shutil.which("golinks")
    if not golinks_path:
        print("Error: golinks command not found in PATH", file=sys.stderr)
        sys.exit(1)

    config_path = get_config_path(args.config)
    ensure_config_exists(config_path)

    # Setup LaunchAgent
    setup_launchagent(golinks_path, args.port, config_path)

    # Unload if already loaded
    subprocess.run(
        ["launchctl", "unload", str(PLIST_PATH)],
        capture_output=True,
    )

    # Load the service
    result = subprocess.run(
        ["launchctl", "load", str(PLIST_PATH)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Error loading service: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"Service started on port {args.port}")
    print(f"Configuration: {config_path}")
    print(f"Logs: {CONFIG_DIR}/stdout.log, {CONFIG_DIR}/stderr.log")


def cmd_stop_service(args: argparse.Namespace) -> None:
    """Handle stop-service subcommand."""
    if not PLIST_PATH.exists():
        print("Service is not installed", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        ["launchctl", "unload", str(PLIST_PATH)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Error stopping service: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print("Service stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Go Links redirect server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run-server subcommand
    run_parser = subparsers.add_parser(
        "run-server",
        help="Run the server directly (foreground)",
    )
    run_parser.add_argument(
        "--config", "-c",
        type=Path,
        help=f"Path to configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    run_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)",
    )
    run_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    run_parser.set_defaults(func=cmd_run_server)

    # start-service subcommand
    start_parser = subparsers.add_parser(
        "start-service",
        help="Start as a background service (macOS LaunchAgent)",
    )
    start_parser.add_argument(
        "--config", "-c",
        type=Path,
        help=f"Path to configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    start_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)",
    )
    start_parser.set_defaults(func=cmd_start_service)

    # stop-service subcommand
    stop_parser = subparsers.add_parser(
        "stop-service",
        help="Stop the background service",
    )
    stop_parser.set_defaults(func=cmd_stop_service)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
