"""Absolute-path entry point for MCP clients, independent of their working directory."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atlas_mcp.server import main

if __name__ == "__main__":
    main()
