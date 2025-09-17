# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

Use uv to run Python code:
```bash
# Run the server
uv run golinks

# Run with custom config
uv run golinks --config /path/to/config.json

# Run with custom port
uv run golinks --port 9000

# Run any Python command
uv run python <script.py>
```

## Linting

```bash
# Run linter
uv run ruff check .

# Fix linting issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

## Architecture

### Core Components

**HTTP Server** (`src/server.py`):
- Uses Python's built-in `http.server` module with custom `GoLinksHandler`
- Handles redirects based on path matching against configured shortcuts
- Hot-reloads configuration on each request (no restart needed)
- Serves web interface at root path showing all available links

**Configuration** (`src/models.py`):
- Pydantic models for type-safe configuration handling
- Supports simple string URLs or template objects with Jinja2 templating
- `LinkTemplate` allows for parameterized URLs with defaults

**Templates** (`src/templates/`):
- Jinja2 templates for the web interface
- `base.html`: Base template with common styles
- `links.html`: Shows all configured shortcuts
- `error.html`: Friendly 404 page for unknown shortcuts

### Key Design Patterns

1. **Hot-reload Configuration**: Config is loaded fresh on each request from JSON file
2. **Template URLs**: Links can use Jinja2 templates with query parameters as variables
3. **Query Parameter Preservation**: Unmatched query params are passed through to destination
4. **No External Dependencies**: Uses Python stdlib where possible (except Jinja2, Pydantic)

### Configuration Format

Simple redirects:
```json
{
  "github": "https://github.com"
}
```

Template redirects with defaults:
```json
{
  "search": {
    "template_url": "https://www.google.com/search?q={{q|default('python')}}",
    "defaults": {
      "q": "python"
    }
  }
}
```