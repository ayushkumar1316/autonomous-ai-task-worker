"""Load environment variables from .env file (no external dependencies)."""
import os
from pathlib import Path


def load_env(env_file: str = ".env") -> dict:
    """Load .env file and return dict of newly loaded vars.
    
    Does NOT override existing environment variables.
    """
    path = Path(env_file)
    if not path.exists():
        return {}

    loaded = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        # Split KEY=VALUE
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Remove quotes if present
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        # Only set if not already in environment
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


if __name__ == "__main__":
    loaded = load_env()
    if loaded:
        print("Loaded from .env:")
        for k, v in loaded.items():
            # Mask the value for safety
            masked = v[:8] + "..." if len(v) > 12 else v
            print(f"  {k} = {masked}")
    else:
        print("No .env file found (or no new vars loaded)")
        print("Create .env from .env.example: cp .env.example .env")
