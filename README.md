# Golinks

A simple local HTTP redirect service that turns short URLs like `go/github` into full URLs.

## Installation

### Install from pypi
```
bash -c "$(curl -fsSL https://raw.githubusercontent.com/haranrk/golinks/master/install.sh)"
```

### Install from source
```bash
# Clone the repository
git clone https://github.com/yourusername/golinks.git
cd golinks

# Run the install script
./install

# Edit the config
vim ~/.config/golinks/config.json
```

## Update

```bash
uv tool upgrade golinks
```

## How it works

The `./install` script does the following:
1. Installs the Python package using uv
2. Adds `127.0.0.1 go` to your `/etc/hosts` file (with sudo permission)
3. Sets up port forwarding from port 80 to 8888 using pfctl (macOS) or iptables (Linux), so you can use `go/shortcut` instead of `go:8888/shortcut`
4. Sets up a LaunchAgent (macOS) or systemd service (Linux) to run the server at startup
5. Starts the golinks server immediately on port 8888

Once installed, golinks runs a lightweight HTTP server that reads shortcuts from a JSON config file at `~/.golinks/config.json` and redirects `http://go/shortcut` to the configured destination URL. The config file is hot-reloaded, so you can add new shortcuts without restarting the server.

## Configuration

The configuration file (`~/.config/golinks/config.json`) supports two types of shortcuts:

### Simple URL Redirects
Map a shortcut directly to a URL:
```json
{
  "github": "https://github.com",
  "mail": "https://gmail.com",
  "calendar": "https://calendar.google.com"
}
```
- `go/github` → `https://github.com`
- `go/mail` → `https://gmail.com`

### Template URLs with Parameters
Use placeholders (`{1}`, `{2}`, etc.) for dynamic URLs:
```json
{
  "repo": {
    "template_url": "https://github.com/{1}/{2}",
    "defaults": {
      "1": "haranrk",
      "2": "golinks"
    }
  }
}
```
- `go/repo` → `https://github.com/haranrk/golinks` (uses defaults)
- `go/repo//otherrepo` → `https://github.com/haranrk/otherrepo` (uses default for 1)
- `go/repo/facebook/` → `https://github.com/facebook/golinks` (uses default for 2)
- `go/repo/facebook/react` → `https://github.com/facebook/react`

Note: If a template parameter doesn't have a default value and isn't provided, it's replaced with an empty string.

### Query Parameter Forwarding
Query parameters are automatically forwarded to the destination:
```json
{
  "search": "https://google.com/search"
}
```
- `go/search?q=golang&num=10` → `https://google.com/search?q=golang&num=10`

## Troubleshooting

If `go/` links stop working, restart the service:

```bash
golinks start-service
```

This will recreate the LaunchAgent and reload the service.
