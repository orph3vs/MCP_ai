"""Expose top-level src package as next_mcp.src when run from repo root."""

from pathlib import Path


__path__ = [str(Path(__file__).resolve().parents[2] / "src")]
