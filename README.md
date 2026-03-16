# OOMOL Cloud Task SDK (Python)

Python SDK for OOMOL Cloud Task API v3.

## Features

- Supports `serverless` task creation
- Covers the same user-facing task APIs as the TypeScript SDK:
  `create_task`, `create_and_wait`, `list_tasks`, `get_latest_tasks`, `get_task`,
  `get_task_result`, `get_dashboard`, `set_tasks_pause`, `upload_file`
- Supports `pause_user_queue`, `resume_user_queue`, and `get_task_detail` aliases
- Retries transient polling failures in `await_result` until timeout or terminal status
- Exposes aligned error types: `ApiError`, `RunTaskError`, `TaskFailedError`,
  `TimeoutError`, `UploadError`
- Exports aligned public typing helpers such as `AwaitOptions`, `BackoffOptions`,
  `ClientOptions`, `UploadOptions`, and `TaskTerminalStatus`

## Installation

```bash
pip install oomol-cloud-task-sdk
```

## Requirements

- Python `>=3.7`
- `requests>=2.25.0`
- `typing_extensions>=4.0.0` on Python 3.7

## Authentication

`api_key` is optional.

- Token auth: pass `api_key`, the client sends `Authorization: Bearer <api_key>`
- Cookie auth: omit `api_key` and use the underlying `requests.Session` cookies

```python
from oomol_cloud_task import OomolTaskClient

client = OomolTaskClient(
    api_key=None,
    default_headers={"x-client": "my-app"},
)
```

## Quick Start

```python
from oomol_cloud_task import BackoffStrategy, OomolTaskClient

client = OomolTaskClient(api_key="YOUR_API_KEY")

response = client.create_and_wait(
    {
        "packageName": "@oomol/my-package",
        "packageVersion": "1.0.0",
        "blockName": "main",
        "inputValues": {"text": "hello"},
    },
    interval_ms=2000,
    timeout_ms=10 * 60 * 1000,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    max_interval_ms=10000,
    on_progress=lambda progress, status: print("progress:", progress, "status:", status),
)

print("taskID:", response.taskID)
if response.result["status"] == "success":
    print("resultURL:", response.result.get("resultURL"))
    print("resultData:", response.result.get("resultData"))
```

## API Overview

Available methods:

- `create_task(request)`
- `create_and_wait(request, interval_ms=3000, timeout_ms=None, backoff_strategy=BackoffStrategy.EXPONENTIAL, max_interval_ms=3000, on_progress=None)`
- `list_tasks(query=None)`
- `get_latest_tasks(workload_ids)`
- `get_task(task_id)` / `get_task_detail(task_id)`
- `get_task_result(task_id)`
- `await_result(task_id, interval_ms=3000, timeout_ms=None, backoff_strategy=BackoffStrategy.EXPONENTIAL, max_interval_ms=3000, on_progress=None)`
- `get_dashboard()`
- `set_tasks_pause(paused)`
- `pause_user_queue()`
- `resume_user_queue()`
- `upload_file(file, upload_base_url=..., retries=3, on_progress=None)`

## Common Examples

Create a task:

```python
client.create_task(
    {
        "packageName": "@oomol/my-package",
        "packageVersion": "1.0.0",
        "blockName": "main",
        "inputValues": {"foo": "bar"},
    }
)
```

Query tasks:

```python
page = client.list_tasks(
    {
        "size": 20,
        "status": "running",
        "taskType": "user",
    }
)

latest = client.get_latest_tasks(
    [
        "550e8400-e29b-41d4-a716-446655440022",
        "550e8400-e29b-41d4-a716-446655440023",
    ]
)

latest2 = client.get_latest_tasks(
    "550e8400-e29b-41d4-a716-446655440022,550e8400-e29b-41d4-a716-446655440023"
)

detail = client.get_task("019234a5-b678-7def-8123-456789abcdef")
result = client.get_task_result("019234a5-b678-7def-8123-456789abcdef")
dashboard = client.get_dashboard()
```

Pause or resume the current user's queue:

```python
client.pause_user_queue()
client.resume_user_queue()

client.set_tasks_pause(True)
client.set_tasks_pause(False)
```

Upload a file:

```python
url = client.upload_file(
    "/path/to/file.pdf",
    retries=3,
    on_progress=lambda progress: print("upload:", progress),
)
```

`upload_file` accepts either:

- a filesystem path
- a seekable binary file object

## Polling Behavior

`await_result` and `create_and_wait` follow the same polling semantics as the TypeScript SDK:

- default polling interval is `3000ms`
- `BackoffStrategy.EXPONENTIAL` is the default
- transient polling request failures are retried
- terminal task failure raises `TaskFailedError`
- timeout raises `TimeoutError`

If polling times out after earlier request failures, the timeout message includes the most recent polling error.

## Errors

```python
from oomol_cloud_task import (
    ApiError,
    RunTaskErrorCode,
    TaskFailedError,
    TimeoutError,
    UploadError,
)

try:
    response = client.create_and_wait(
        {
            "packageName": "@oomol/my-package",
            "packageVersion": "1.0.0",
            "blockName": "main",
        },
        timeout_ms=60_000,
    )
except TaskFailedError as err:
    print(err.taskID, err.code, err.status_code, err.detail)
    if err.code == RunTaskErrorCode.INSUFFICIENT_QUOTA:
        print("insufficient quota")
except TimeoutError as err:
    print("timeout:", err)
except UploadError as err:
    print("upload error:", err.code, err.status_code, err)
except ApiError as err:
    print("api error:", err.status, err.body)
```

## License

MIT
