"""Parsers for the open source files in data/raw/ (see pipeline/download.py)."""

from pathlib import Path

RAW = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
