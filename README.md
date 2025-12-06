# Oomol Cloud Task SDK (Python)

A lightweight, developer-friendly Python SDK for [Oomol Cloud Task API](https://cloud-task.oomol.com/v1).

## Installation

```bash
pip install oomol-cloud-task-sdk
```

## Requirements

- Python >= 3.7
- requests >= 2.25.0

## Quick Start

```python
from oomol_cloud_task import OomolTaskClient, BackoffStrategy

client = OomolTaskClient(api_key="YOUR_API_KEY")

task_id, result = client.create_and_wait(
    applet_id="your-applet-id",
    input_values={
        "input_pdf": "...",
        "output_path": "..."
    },
    on_progress=lambda p, s: print(f"Status: {s}, Progress: {p}%")
)

print(f"Task {task_id} completed!")
print(result)
```

## Features

- Automatic polling with `create_and_wait`
- Fixed and exponential backoff strategies
- Progress callback support
- Full type hints

## API Reference

### OomolTaskClient

#### Constructor

```python
client = OomolTaskClient(
    api_key="YOUR_API_KEY",
    base_url="https://cloud-task.oomol.com/v1",  # optional
    default_headers={"X-Custom-Header": "value"}  # optional
)
```

#### Methods

##### `create_task()`

Creates a task and returns the task ID.

```python
task_id = client.create_task(
    applet_id="your-applet-id",
    input_values={"key": "value"},
    webhook_url="https://your-webhook.com",  # optional
    metadata={"custom": "data"}  # optional
)
```

##### `get_task_result()`

Fetches the current result/status of a task.

```python
result = client.get_task_result(task_id)
```

##### `await_result()`

Polls for the task result until completion or timeout.

```python
result = client.await_result(
    task_id="your-task-id",
    interval_ms=3000,           # polling interval (default: 3000)
    timeout_ms=60000,           # optional timeout
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    max_interval_ms=3000,       # max interval for exponential backoff
    on_progress=callback_fn     # optional progress callback
)
```

##### `create_and_wait()`

Creates a task and waits for its completion. Returns `(task_id, result)`.

```python
task_id, result = client.create_and_wait(
    applet_id="your-applet-id",
    input_values={"key": "value"},
    webhook_url=None,           # optional
    metadata=None,              # optional
    interval_ms=3000,
    timeout_ms=None,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    max_interval_ms=3000,
    on_progress=None
)
```

### Types

#### BackoffStrategy

```python
from oomol_cloud_task import BackoffStrategy

BackoffStrategy.FIXED        # Fixed interval polling
BackoffStrategy.EXPONENTIAL  # Exponential backoff (1.5x multiplier)
```

#### TaskStatus

```python
from oomol_cloud_task import TaskStatus

TaskStatus.PENDING   # Task is pending
TaskStatus.RUNNING   # Task is running
TaskStatus.SUCCESS   # Task completed successfully
TaskStatus.FAILED    # Task failed
```

### Exceptions

```python
from oomol_cloud_task import ApiError, TaskFailedError, TimeoutError

try:
    task_id, result = client.create_and_wait(...)
except ApiError as e:
    print(f"API Error: {e}, Status: {e.status}, Body: {e.body}")
except TaskFailedError as e:
    print(f"Task {e.task_id} failed: {e.detail}")
except TimeoutError as e:
    print(f"Operation timed out: {e}")
```

## License

MIT
