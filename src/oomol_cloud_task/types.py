"""Shared types for the Oomol Cloud Task SDK."""

from enum import Enum
from typing import Any, Callable, Dict, Optional


class BackoffStrategy(Enum):
    """Polling interval backoff strategy."""

    # Keep a fixed interval between polls.
    FIXED = "fixed"
    # Increase interval exponentially between polls (recommended for long-running tasks).
    EXPONENTIAL = "exp"


class TaskStatus(str, Enum):
    """Task lifecycle states returned by the API."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


# Type aliases used across the client API.
InputValues = Dict[str, Any]
Metadata = Dict[str, Any]
TaskResult = Dict[str, Any]
ProgressCallback = Callable[[Optional[float], str], None]
