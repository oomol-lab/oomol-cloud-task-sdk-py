import time
import requests
from typing import Optional, Callable, Dict, Any, Tuple
from .errors import ApiError, TaskFailedError, TimeoutError
from .types import BackoffStrategy, TaskStatus, InputValues, Metadata

DEFAULT_BASE_URL = "https://cloud-task.oomol.com/v1"

class OomolTaskClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        default_headers: Optional[Dict[str, str]] = None
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_headers = default_headers or {}
        self.session = requests.Session()

    def create_task(
        self,
        applet_id: str,
        input_values: InputValues,
        webhook_url: Optional[str] = None,
        metadata: Optional[Metadata] = None
    ) -> str:
        """
        Creates a task and returns the task ID.
        """
        url = f"{self.base_url}/task/applet"
        
        body = {
            "appletID": applet_id,
            "inputValues": input_values
        }
        if webhook_url:
            body["webhookUrl"] = webhook_url
        if metadata:
            body["metadata"] = metadata

        headers = self._get_headers()
        
        response = self.session.post(url, json=body, headers=headers)
        
        if not response.ok:
            self._handle_error(response)

        data = response.json()
        return data["taskID"]

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        Fetches the result of a task.
        """
        url = f"{self.base_url}/task/{task_id}/result"
        headers = self._get_headers()
        
        response = self.session.get(url, headers=headers)
        
        if not response.ok:
            self._handle_error(response)
            
        return response.json()

    def await_result(
        self,
        task_id: str,
        interval_ms: int = 2000,
        timeout_ms: Optional[int] = None,
        backoff_strategy: BackoffStrategy = BackoffStrategy.FIXED,
        max_interval_ms: int = 15000,
        on_progress: Optional[Callable[[Optional[float], str], None]] = None
    ) -> Dict[str, Any]:
        """
        Polls for the task result until completion or timeout.
        """
        start_time = time.time()
        attempt = 0
        current_interval = interval_ms / 1000.0
        max_interval = max_interval_ms / 1000.0

        while True:
            # Check timeout
            if timeout_ms is not None:
                elapsed = (time.time() - start_time) * 1000
                if elapsed > timeout_ms:
                    raise TimeoutError()

            result = self.get_task_result(task_id)
            status = result.get("status")
            progress = result.get("progress")

            if status == TaskStatus.SUCCESS.value:
                return result
            
            if status == TaskStatus.FAILED.value:
                raise TaskFailedError(task_id, result.get("error") or result)

            if on_progress:
                on_progress(progress, status)

            attempt += 1
            
            # Backoff logic
            if backoff_strategy == BackoffStrategy.EXPONENTIAL:
                # 1.5x multiplier
                next_interval = min(max_interval, (interval_ms / 1000.0) * (1.5 ** attempt))
            else:
                next_interval = current_interval

            time.sleep(next_interval)

    def create_and_wait(
        self,
        applet_id: str,
        input_values: InputValues,
        webhook_url: Optional[str] = None,
        metadata: Optional[Metadata] = None,
        interval_ms: int = 2000,
        timeout_ms: Optional[int] = None,
        backoff_strategy: BackoffStrategy = BackoffStrategy.FIXED,
        max_interval_ms: int = 15000,
        on_progress: Optional[Callable[[Optional[float], str], None]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Creates a task and waits for its completion.
        Returns (task_id, result).
        """
        task_id = self.create_task(applet_id, input_values, webhook_url, metadata)
        result = self.await_result(
            task_id=task_id,
            interval_ms=interval_ms,
            timeout_ms=timeout_ms,
            backoff_strategy=backoff_strategy,
            max_interval_ms=max_interval_ms,
            on_progress=on_progress
        )
        return task_id, result

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        headers.update(self.default_headers)
        return headers

    def _handle_error(self, response: requests.Response):
        try:
            body = response.json()
        except ValueError:
            body = response.text
        raise ApiError(f"Request failed: {response.status_code}", response.status_code, body)
