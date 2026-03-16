from typing import Any, Optional


class ApiError(Exception):
    def __init__(self, message: str, status: int, body: Optional[Any] = None):
        super().__init__(message)
        self.status = status
        self.body = body


class RunTaskError(Exception):
    def __init__(self, message: str, code: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.statusCode = status_code


class TaskFailedError(RunTaskError):
    def __init__(
        self,
        task_id: str,
        detail: Optional[Any] = None,
        message: str = "Task execution failed",
        code: Optional[str] = None,
        status_code: Optional[int] = None,
    ):
        super().__init__(message, code=code, status_code=status_code)
        self.task_id = task_id
        self.taskID = task_id
        self.detail = detail


class TimeoutError(Exception):
    def __init__(self, message: str = "Operation timed out"):
        super().__init__(message)


class UploadError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.statusCode = status_code
        self.code = code
