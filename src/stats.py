"""Visit statistics persistence for Go Links."""

import json
from pathlib import Path


def get_stats_path(config_path: Path) -> Path:
    """Return the stats file path alongside the config file."""
    return config_path.parent / "stats.json"


def load_stats(stats_path: Path) -> dict[str, int]:
    """Read stats from JSON file. Returns empty dict if missing or malformed."""
    try:
        return json.loads(stats_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_stats(stats_path: Path, stats: dict[str, int]) -> None:
    """Write stats to JSON file."""
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
        f.write("\n")


def increment_stat(stats_path: Path, shortcut: str) -> None:
    """Increment visit count for a shortcut."""
    stats = load_stats(stats_path)
    stats[shortcut] = stats.get(shortcut, 0) + 1
    save_stats(stats_path, stats)
