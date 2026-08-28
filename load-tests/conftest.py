"""Pytest configuration for load-tests.

Adds the load-tests directory to sys.path so that websocket_load can be
imported directly as a module (the directory name 'load-tests' contains a
hyphen and is not a valid Python package identifier).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `import websocket_load` from within the load-tests directory
_LOAD_TESTS_DIR = Path(__file__).parent
if str(_LOAD_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_LOAD_TESTS_DIR))
