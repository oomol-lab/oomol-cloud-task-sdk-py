from enum import Enum
from typing import Dict, Optional, Any, Union

class BackoffStrategy(Enum):
    FIXED = "fixed"
    EXPONENTIAL = "exp"

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

# Type aliases for better readability
InputValues = Dict[str, Any]
Metadata = Dict[str, Any]
