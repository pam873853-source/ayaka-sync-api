"""Vercel entrypoint. Vercel's Python runtime detects the top-level ``app``."""
from backend.main import app  # noqa: F401
