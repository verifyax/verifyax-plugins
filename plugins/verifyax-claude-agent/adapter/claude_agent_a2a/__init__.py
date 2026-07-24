"""Expose a local Claude Code agent over A2A for evaluation by VerifyAX."""

from .backend import ClaudeAgentError, ClaudeCodeBackend
from .server import create_app, get_app

__all__ = ["ClaudeCodeBackend", "ClaudeAgentError", "create_app", "get_app"]
