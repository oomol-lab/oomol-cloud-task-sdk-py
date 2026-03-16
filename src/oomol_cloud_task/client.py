from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union, cast
from urllib.parse import quote

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency-light test envs
    requests = None  # type: ignore[assignment]

REQUESTS_REQUEST_EXCEPTION = requests.RequestException if requests is not None else OSError

from .errors import ApiError, TaskFailedError, TimeoutError, UploadError
from .types import (
    BackoffStrategy,
    CreateAndWaitResponse,
    CreateTaskRequest,
    DashboardResponse,
    InProgressTaskStatus,
    LatestTasksResponse,
    ListTasksQuery,
    ProgressCallback,
    RunTaskErrorCode,
    SetTasksPauseResponse,
    TaskCreateResponse,
    TaskDetailResponse,
    TaskListResponse,
    TaskResult,
    TaskResultResponse,
    TaskResultSuccess,
    TaskStatus,
    UploadProgressCallback,
    UploadSource,
)

DEFAULT_BASE_URL = "https://cloud-task.oomol.com"
DEFAULT_UPLOAD_BASE_URL = "https://llm.oomol.com/api/tasks/files/remote-cache"


class OomolTaskClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        default_headers: Optional[Dict[str, str]] = None,
        session: Optional["requests.Session"] = None,
    ):
        self.api_key = api_key
        self.base_url = self._normalize_base_url(base_url)
        self.default_headers = default_headers or {}
        if session is not None:
            self.session = session
        elif requests is not None:
            self.session = requests.Session()
        else:
            raise ModuleNotFoundError(
                "requests is required to create a default session. Install requests or pass a custom session."
            )

    def create_task(self, request: CreateTaskRequest) -> TaskCreateResponse:
        response = self._request_json(
            "POST",
            "/v3/users/me/tasks",
            json=self._normalize_create_task_request(request),
        )
        return cast(TaskCreateResponse, response)

    def list_tasks(self, query: Optional[ListTasksQuery] = None) -> TaskListResponse:
        response = self._request_json(
            "GET",
            "/v3/users/me/tasks",
            params=self._build_tasks_query_params(query or {}),
        )
        return cast(TaskListResponse, response)

    def get_latest_tasks(self, workload_ids: Union[List[str], str]) -> LatestTasksResponse:
        response = self._request_json(
            "GET",
            "/v3/users/me/tasks/latest",
            params={"workloadIDs": self._normalize_workload_ids(workload_ids)},
        )
        return cast(LatestTasksResponse, response)

    def get_dashboard(self) -> DashboardResponse:
        response = self._request_json("GET", "/v3/users/me/dashboard")
        return cast(DashboardResponse, response)

    def set_tasks_pause(self, paused: bool) -> SetTasksPauseResponse:
        path = "/v3/user/pause" if paused else "/v3/user/resume"
        response = self._request_json("POST", path, json={})
        return cast(SetTasksPauseResponse, response)

    def pause_user_queue(self) -> SetTasksPauseResponse:
        return self.set_tasks_pause(True)

    def resume_user_queue(self) -> SetTasksPauseResponse:
        return self.set_tasks_pause(False)

    def get_task(self, task_id: str) -> TaskDetailResponse:
        response = self._request_json("GET", "/v3/users/me/tasks/{task_id}".format(task_id=quote(task_id, safe="")))
        return cast(TaskDetailResponse, response)

    def get_task_detail(self, task_id: str) -> TaskDetailResponse:
        return self.get_task(task_id)

    def get_task_result(self, task_id: str) -> TaskResultResponse:
        response = self._request_json(
            "GET",
            "/v3/users/me/tasks/{task_id}/result".format(task_id=quote(task_id, safe="")),
        )
        return cast(TaskResultResponse, response)

    def await_result(
        self,
        task_id: str,
        interval_ms: int = 3000,
        timeout_ms: Optional[int] = None,
        backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
        max_interval_ms: int = 3000,
        on_progress: Optional[ProgressCallback] = None,
    ) -> TaskResultSuccess:
        start_time = time.monotonic()
        attempt = 0
        last_polling_request_error = None

        while True:
            if timeout_ms is not None and self._elapsed_ms(start_time) > timeout_ms:
                raise self._create_timeout_error_with_last_polling_error(last_polling_request_error, timeout_ms)

            try:
                result = cast(TaskResult, self.get_task_result(task_id))
            except Exception as error:
                last_polling_request_error = error
                attempt += 1
                next_interval = self._compute_next_interval_seconds(
                    attempt=attempt,
                    interval_ms=interval_ms,
                    max_interval_ms=max_interval_ms,
                    strategy=backoff_strategy,
                )
                self._sleep_with_timeout(
                    next_interval,
                    start_time=start_time,
                    timeout_ms=timeout_ms,
                    last_polling_request_error=last_polling_request_error,
                )
                continue

            status = result["status"]
            if status == TaskStatus.SUCCESS.value:
                return cast(TaskResultSuccess, result)

            if status == TaskStatus.FAILED.value:
                raise self._create_task_failed_error(task_id, result.get("error") or result)

            if on_progress:
                on_progress(float(result["progress"]), cast(InProgressTaskStatus, status))

            attempt += 1
            next_interval = self._compute_next_interval_seconds(
                attempt=attempt,
                interval_ms=interval_ms,
                max_interval_ms=max_interval_ms,
                strategy=backoff_strategy,
            )
            self._sleep_with_timeout(
                next_interval,
                start_time=start_time,
                timeout_ms=timeout_ms,
                last_polling_request_error=last_polling_request_error,
            )

    def create_and_wait(
        self,
        request: CreateTaskRequest,
        interval_ms: int = 3000,
        timeout_ms: Optional[int] = None,
        backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
        max_interval_ms: int = 3000,
        on_progress: Optional[ProgressCallback] = None,
    ) -> CreateAndWaitResponse:
        task_id = self.create_task(request)["taskID"]
        result = self.await_result(
            task_id=task_id,
            interval_ms=interval_ms,
            timeout_ms=timeout_ms,
            backoff_strategy=backoff_strategy,
            max_interval_ms=max_interval_ms,
            on_progress=on_progress,
        )
        return CreateAndWaitResponse(taskID=task_id, result=result)

    def upload_file(
        self,
        file: UploadSource,
        upload_base_url: str = DEFAULT_UPLOAD_BASE_URL,
        retries: int = 3,
        on_progress: Optional[UploadProgressCallback] = None,
    ) -> str:
        file_handle, should_close, file_name, file_size = self._open_upload_source(file)
        try:
            init_response = self._upload_init(upload_base_url, file_name=file_name, file_size=file_size)
            upload_data = cast(Dict[str, Any], init_response["data"])
            upload_id = str(upload_data["upload_id"])
            part_size = int(upload_data["part_size"])
            total_parts = int(upload_data["total_parts"])
            presigned_urls = cast(Dict[Union[int, str], str], upload_data["presigned_urls"])

            uploaded_bytes = 0
            for part_number in range(1, total_parts + 1):
                start = (part_number - 1) * part_size
                end = min(start + part_size, file_size)
                part_data = self._read_part(file_handle, end - start)
                presigned_url = presigned_urls.get(part_number) or presigned_urls.get(str(part_number))
                if not presigned_url:
                    raise UploadError(
                        "Missing presigned URL for part {part_number}".format(part_number=part_number),
                        code="MISSING_PRESIGNED_URL",
                    )
                self._upload_part(part_data, presigned_url, retries=retries)
                uploaded_bytes += len(part_data)
                if on_progress:
                    progress = math.floor((uploaded_bytes / file_size) * 100) if file_size > 0 else 0
                    on_progress(99 if progress >= 100 else progress)

            final_url = self._upload_final(upload_base_url, upload_id)
            if on_progress:
                on_progress(100)
            return final_url
        finally:
            if should_close:
                file_handle.close()

    def _request_json(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        response = self._call_session(
            method,
            self._build_url(path),
            json=json,
            params=params,
            headers=self._build_headers({"Content-Type": "application/json"} if json is not None else None),
        )
        if not response.ok:
            self._raise_api_error(response, "Request failed: {status}")
        return self._parse_json_body(response)

    def _call_session(
        self,
        method: str,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[bytes] = None,
    ) -> "requests.Response":
        request_method = getattr(self.session, method.lower())
        kwargs = {}
        if json is not None:
            kwargs["json"] = json
        if params is not None:
            kwargs["params"] = params
        if headers is not None:
            kwargs["headers"] = headers
        if data is not None:
            kwargs["data"] = data
        return cast("requests.Response", request_method(url, **kwargs))

    def _normalize_create_task_request(self, request: CreateTaskRequest) -> Dict[str, Any]:
        body = {
            "type": "serverless",
            "packageName": request["packageName"],
            "packageVersion": request["packageVersion"],
            "blockName": request["blockName"],
        }
        if "inputValues" in request:
            body["inputValues"] = request["inputValues"]
        return body

    def _build_tasks_query_params(self, query: ListTasksQuery) -> Dict[str, str]:
        params: Dict[str, str] = {}
        size = query.get("size")
        if size is not None:
            if not isinstance(size, int) or size < 1 or size > 100:
                raise ValueError("size must be an integer between 1 and 100")
            params["size"] = str(size)

        for key in ("nextToken", "status", "taskType", "workload", "workloadID", "packageID"):
            value = query.get(key)
            if value:
                params[key] = str(value)
        return params

    def _normalize_workload_ids(self, workload_ids: Union[List[str], str]) -> str:
        if isinstance(workload_ids, list):
            if not workload_ids:
                raise ValueError("workload_ids cannot be empty")
            if len(workload_ids) > 50:
                raise ValueError("workload_ids cannot exceed 50 items")
            normalized_ids = [item.strip() for item in workload_ids]
            if any(not item for item in normalized_ids):
                raise ValueError("workload_ids must not contain empty items")
            return ",".join(normalized_ids)

        normalized = workload_ids.strip()
        if not normalized:
            raise ValueError("workload_ids cannot be empty")
        return normalized

    def _compute_next_interval_seconds(
        self,
        attempt: int,
        interval_ms: int,
        max_interval_ms: int,
        strategy: BackoffStrategy,
    ) -> float:
        interval_base = interval_ms / 1000.0
        max_interval = max_interval_ms / 1000.0
        if strategy == BackoffStrategy.EXPONENTIAL:
            return min(max_interval, interval_base * (1.5 ** attempt))
        return interval_base

    def _sleep_with_timeout(
        self,
        delay_seconds: float,
        start_time: float,
        timeout_ms: Optional[int],
        last_polling_request_error: Optional[Exception],
    ) -> None:
        if timeout_ms is None:
            time.sleep(delay_seconds)
            return

        remaining_ms = timeout_ms - self._elapsed_ms(start_time)
        if remaining_ms <= 0:
            raise self._create_timeout_error_with_last_polling_error(last_polling_request_error, timeout_ms)

        time.sleep(min(delay_seconds, remaining_ms / 1000.0))

    def _elapsed_ms(self, start_time: float) -> float:
        return (time.monotonic() - start_time) * 1000

    def _open_upload_source(self, file: UploadSource) -> Tuple[BinaryIO, bool, str, int]:
        if isinstance(file, (str, os.PathLike)):
            path = Path(os.fspath(file))
            return path.open("rb"), True, path.name, path.stat().st_size

        file_handle = cast(BinaryIO, file)
        if not hasattr(file_handle, "read") or not hasattr(file_handle, "seek") or not hasattr(file_handle, "tell"):
            raise ValueError("upload_file expects a path or a seekable binary file object")

        file_handle.seek(0, os.SEEK_END)
        file_size = file_handle.tell()
        file_handle.seek(0)
        file_name = getattr(file_handle, "name", "upload.bin")
        return file_handle, False, Path(str(file_name)).name, file_size

    def _read_part(self, file_handle: BinaryIO, size: int) -> bytes:
        part = file_handle.read(size)
        if isinstance(part, bytes):
            return part
        raise ValueError("upload_file expects a binary file object")

    def _upload_init(self, upload_base_url: str, file_name: str, file_size: int) -> Dict[str, Any]:
        extension = Path(file_name).suffix or "."
        response = self._call_session(
            "POST",
            "{base}/init".format(base=upload_base_url.rstrip("/")),
            json={
                "file_extension": extension,
                "size": file_size,
            },
            headers=self._build_headers({"Content-Type": "application/json"}),
        )
        if not response.ok:
            raise UploadError(
                "Failed to initialize upload: {status}".format(status=response.status_code),
                status_code=response.status_code,
                code="INIT_UPLOAD_FAILED",
            )
        return cast(Dict[str, Any], self._parse_json_body(response) or {})

    def _upload_part(self, part_data: bytes, presigned_url: str, retries: int) -> None:
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                response = self._call_session(
                    "PUT",
                    presigned_url,
                    data=part_data,
                    headers={"Content-Type": "application/octet-stream"},
                )
                if response.ok:
                    return
                last_error = UploadError(
                    "Upload failed with status {status}".format(status=response.status_code),
                    status_code=response.status_code,
                    code="UPLOAD_FAILED",
                )
            except REQUESTS_REQUEST_EXCEPTION:
                last_error = UploadError("Network error during upload", code="NETWORK_ERROR")

            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 30))

        if isinstance(last_error, UploadError):
            raise UploadError(
                "Failed after {retries} attempts: {message}".format(
                    retries=retries,
                    message=str(last_error),
                ),
                code="RETRY_EXHAUSTED",
            )
        raise UploadError("Failed after {retries} attempts: Unknown error".format(retries=retries), code="RETRY_EXHAUSTED")

    def _upload_final(self, upload_base_url: str, upload_id: str) -> str:
        response = self._call_session(
            "GET",
            "{base}/{upload_id}/url".format(
                base=upload_base_url.rstrip("/"),
                upload_id=quote(upload_id, safe=""),
            ),
            headers=self._build_headers(),
        )
        if not response.ok:
            raise UploadError(
                "Failed to get upload URL: {status}".format(status=response.status_code),
                status_code=response.status_code,
                code="GET_UPLOAD_URL_FAILED",
            )

        result = cast(Dict[str, Any], self._parse_json_body(response) or {})
        data = cast(Dict[str, Any], result.get("data") or {})
        return cast(str, data["url"])

    def _build_url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else "/{path}".format(path=path)
        return "{base}{path}".format(base=self.base_url, path=normalized_path)

    def _normalize_base_url(self, base_url: str) -> str:
        trimmed = base_url.rstrip("/")
        for suffix in ("/v1", "/v3"):
            if trimmed.endswith(suffix):
                return trimmed[: -len(suffix)]
        return trimmed

    def _build_headers(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        merged = dict(self.default_headers)
        if self.api_key:
            merged["Authorization"] = "Bearer {api_key}".format(api_key=self.api_key)
        if headers:
            merged.update(headers)
        return merged

    def _parse_json_body(self, response: "requests.Response") -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    def _raise_api_error(self, response: "requests.Response", default_message: str) -> None:
        body = self._parse_json_body(response)
        message = default_message.format(status=response.status_code)
        if isinstance(body, dict) and body.get("message"):
            message = str(body["message"])
        raise ApiError(message, response.status_code, body)

    def _create_task_failed_error(self, task_id: str, detail: Any) -> TaskFailedError:
        backend_message = self._extract_backend_error_message(detail)
        normalized_message = backend_message or "Unknown error"
        is_insufficient_quota = self._is_insufficient_quota_message(normalized_message)
        return TaskFailedError(
            task_id,
            detail=detail,
            message="Task failed: {message}".format(message=normalized_message),
            code=RunTaskErrorCode.INSUFFICIENT_QUOTA.value if is_insufficient_quota else None,
            status_code=402 if is_insufficient_quota else None,
        )

    def _create_timeout_error_with_last_polling_error(
        self,
        last_polling_request_error: Optional[Exception],
        timeout_ms: Optional[int],
    ) -> TimeoutError:
        if isinstance(timeout_ms, int) and timeout_ms > 0:
            minutes = max(1, int(round(timeout_ms / 60000.0)))
            base_message = "Task polling timeout after {minutes} minutes".format(minutes=minutes)
        else:
            base_message = "Operation timed out"

        if not last_polling_request_error:
            return TimeoutError(base_message)

        reason = self._extract_backend_error_message(last_polling_request_error) or "unknown polling request error"
        return TimeoutError("{base}. Last polling request error: {reason}".format(base=base_message, reason=reason))

    def _extract_backend_error_message(self, detail: Any) -> Optional[str]:
        if isinstance(detail, ApiError):
            body_message = self._extract_message_from_unknown(detail.body)
            if body_message:
                return body_message
            return str(detail)

        if isinstance(detail, Exception):
            message = str(detail).strip()
            return message or None

        return self._extract_message_from_unknown(detail)

    def _extract_message_from_unknown(self, detail: Any) -> Optional[str]:
        if isinstance(detail, str):
            message = detail.strip()
            return message or None

        if not isinstance(detail, dict):
            return None

        for key in ("message", "error"):
            value = detail.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _is_insufficient_quota_message(self, message: str) -> bool:
        lower_message = message.lower()
        return any(
            needle in lower_message
            for needle in (
                "insufficient",
                "quota",
                "balance",
                "credit",
                "余额",
                "点数",
                "费用",
            )
        )
