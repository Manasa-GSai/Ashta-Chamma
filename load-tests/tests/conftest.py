"""Pytest conftest for load-tests/tests.

Re-export the sys.path setup from the parent conftest so that the
websocket_load module can be imported when tests are run from either the
load-tests/ directory or the repo root.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The websocket_load module lives directly in load-tests/
_LOAD_TESTS_DIR = Path(__file__).parent.parent
if str(_LOAD_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_LOAD_TESTS_DIR))
