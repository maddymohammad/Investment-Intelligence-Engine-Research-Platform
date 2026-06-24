"""Shared pytest fixtures and configuration."""
import os
import sys

# Ensure project root is in path for all test runs
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Minimal env vars so Settings can be instantiated without a real .env
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-placeholder-for-tests")
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("AI_PROVIDER", "anthropic")
os.environ.setdefault("LOG_LEVEL", "WARNING")
