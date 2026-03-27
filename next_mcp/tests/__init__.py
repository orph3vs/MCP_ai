"""Expose top-level tests package as next_mcp.tests when run from repo root."""

from pathlib import Path


__path__ = [str(Path(__file__).resolve().parents[2] / "tests")]
