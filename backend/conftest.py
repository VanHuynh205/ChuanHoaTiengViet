"""Pytest configuration and fixtures for backend tests."""

import sys
from pathlib import Path

# Add backend to Python path for imports
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def pytest_configure(config):
    """Configure pytest with custom temp directory to avoid Windows permission issues."""
    # Set basetemp to avoid Windows permission issues with default system temp
    if not config.getoption("--basetemp", default=None):
        test_tmp = backend_dir.parent / ".test_tmp"
        config.option.basetemp = str(test_tmp)
