# Oomol Cloud Task SDK (Python)

A lightweight, developer-friendly Python SDK for `https://cloud-task.oomol.com/v1`.

## Installation

```bash
pip install oomol-cloud-task-sdk
```

(Note: You need to build the package locally first or publish it to PyPI)

## Usage

```python
from oomol_cloud_task import OomolTaskClient, BackoffStrategy

client = OomolTaskClient(api_key="YOUR_API_KEY")

task_id, result = client.create_and_wait(
    applet_id="54dfbca0-6b2a-4738-bc38-c602981d9be6",
    input_values={
        "input_pdf": "...",
        "output_path": "..."
    },
    interval_ms=2000,
    backoff_strategy=BackoffStrategy.EXPONENTIAL
)

print(result)
```

## Features

- **Automatic Polling**: `create_and_wait` handles creation and polling in one step.
- **Backoff Strategies**: Supports `Fixed` and `Exponential` backoff to reduce server load.
- **Type Hints**: Fully typed for better IDE support.
