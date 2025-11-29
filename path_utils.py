import os
import sys

_BASE_PATH = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))


def resource_path(*relative_parts):
    """Return an absolute path inside the bundled/resources directory."""
    if not relative_parts:
        return _BASE_PATH
    return os.path.join(_BASE_PATH, *relative_parts)


def data_path(*relative_parts):
    """
    Return a path inside the user-specific data directory.
    Used for writable files such as leaderboard.json when running a packaged build.
    """
    base = os.path.join(os.path.expanduser('~'), 'FruitNinjaAR')
    os.makedirs(base, exist_ok=True)
    if not relative_parts:
        return base
    return os.path.join(base, *relative_parts)

