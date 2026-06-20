"""
Utility helpers for locating data files regardless of working directory.
Use DATA_DIR to construct paths portably.
"""

from __future__ import annotations

from pathlib import Path

# Root of the repository — two levels up from this file (src/utils/file_loader.py)
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

DATA_DIR: Path = REPO_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
INJECTED_DIR: Path = DATA_DIR / "injected"
TEST_DIR: Path = DATA_DIR / "test"


def raw_file(name: str) -> Path:
    """Return the absolute path to a file in data/raw/."""
    return RAW_DIR / name


def test_file(name: str) -> Path:
    """Return the absolute path to a file in data/test/."""
    return TEST_DIR / name


def injected_file(name: str) -> Path:
    """Return the absolute path to a file in data/injected/."""
    return INJECTED_DIR / name
