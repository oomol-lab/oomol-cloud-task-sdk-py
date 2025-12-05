class ApiError(Exception):
    def __init__(self, message: str, status: int, body: any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class TaskFailedError(Exception):
    def __init__(self, task_id: str, detail: any = None):
        super().__init__(f"Task execution failed: {task_id}")
        self.task_id = task_id
        self.detail = detail


class TimeoutError(Exception):
    def __init__(self, message: str = "Operation timed out"):
        super().__init__(message)
