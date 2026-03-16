import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from oomol_cloud_task import (  # noqa: E402
    ApiError,
    AwaitOptions,
    BackoffStrategy,
    BackoffOptions,
    ClientOptions,
    OomolTaskClient,
    RunTaskErrorCode,
    TaskFailedError,
    TaskTerminalStatus,
    TimeoutError,
    UploadOptions,
)


class FakeResponse:
    def __init__(self, ok=True, status_code=200, json_data=None):
        self.ok = ok
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


class FakeSession:
    def __init__(self, get_responses=None, post_responses=None, put_responses=None):
        self.responses = {
            "get": list(get_responses or []),
            "post": list(post_responses or []),
            "put": list(put_responses or []),
        }
        self.calls = {"get": [], "post": [], "put": []}

    def get(self, url, **kwargs):
        self.calls["get"].append({"url": url, **kwargs})
        return self.responses["get"].pop(0)

    def post(self, url, **kwargs):
        self.calls["post"].append({"url": url, **kwargs})
        return self.responses["post"].pop(0)

    def put(self, url, **kwargs):
        self.calls["put"].append({"url": url, **kwargs})
        return self.responses["put"].pop(0)


class OomolTaskClientTests(unittest.TestCase):
    def test_aligned_types_are_exported(self):
        self.assertIn("backoff", AwaitOptions.__annotations__)
        self.assertIn("strategy", BackoffOptions.__annotations__)
        self.assertIn("session", ClientOptions.__annotations__)
        self.assertIn("retries", UploadOptions.__annotations__)
        self.assertIn("success", TaskTerminalStatus.__args__)
        self.assertIn("failed", TaskTerminalStatus.__args__)

    def test_create_task_normalizes_serverless_request(self):
        client = OomolTaskClient(api_key="test-key", session=FakeSession(post_responses=[FakeResponse(json_data={"taskID": "task-1"})]))

        task = client.create_task(
            {
                "packageName": "@oomol/my-package",
                "packageVersion": "1.0.0",
                "blockName": "main",
            }
        )

        self.assertEqual(task, {"taskID": "task-1"})
        self.assertEqual(
            client.session.calls["post"][0]["json"],
            {
                "type": "serverless",
                "packageName": "@oomol/my-package",
                "packageVersion": "1.0.0",
                "blockName": "main",
            },
        )
        self.assertEqual(
            client.session.calls["post"][0]["url"],
            "https://cloud-task.oomol.com/v3/users/me/tasks",
        )

    def test_list_tasks_validates_size(self):
        client = OomolTaskClient(api_key="test-key", session=FakeSession())

        with self.assertRaises(ValueError) as ctx:
            client.list_tasks({"size": 101})

        self.assertEqual(str(ctx.exception), "size must be an integer between 1 and 100")

    def test_get_latest_tasks_validates_workload_ids(self):
        client = OomolTaskClient(api_key="test-key", session=FakeSession())

        with self.assertRaises(ValueError) as ctx:
            client.get_latest_tasks([])

        self.assertEqual(str(ctx.exception), "workload_ids cannot be empty")

    @patch("oomol_cloud_task.client.time.sleep", return_value=None)
    def test_await_result_retries_transient_polling_error(self, _sleep):
        session = FakeSession(
            get_responses=[
                FakeResponse(ok=False, status_code=503, json_data={"message": "server busy"}),
                FakeResponse(json_data={"status": "queued", "progress": 10}),
                FakeResponse(json_data={"status": "success", "resultURL": None, "resultData": [{"ok": True}]}),
            ]
        )
        client = OomolTaskClient(api_key="test-key", session=session)
        progress_events = []

        result = client.await_result(
            "task-1",
            interval_ms=1,
            backoff_strategy=BackoffStrategy.FIXED,
            on_progress=lambda progress, status: progress_events.append((progress, status)),
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(progress_events, [(10.0, "queued")])
        self.assertEqual(len(session.calls["get"]), 3)

    def test_await_result_raises_task_failed_error_with_quota_metadata(self):
        session = FakeSession(get_responses=[FakeResponse(json_data={"status": "failed", "error": "Insufficient quota"})])
        client = OomolTaskClient(api_key="test-key", session=session)

        with self.assertRaises(TaskFailedError) as ctx:
            client.await_result("task-1", interval_ms=1)

        self.assertEqual(str(ctx.exception), "Task failed: Insufficient quota")
        self.assertEqual(ctx.exception.taskID, "task-1")
        self.assertEqual(ctx.exception.code, RunTaskErrorCode.INSUFFICIENT_QUOTA.value)
        self.assertEqual(ctx.exception.status_code, 402)

    @patch("oomol_cloud_task.client.time.sleep", return_value=None)
    def test_await_result_timeout_includes_last_polling_error(self, _sleep):
        session = FakeSession(get_responses=[FakeResponse(ok=False, status_code=503, json_data={"message": "server busy"})])
        client = OomolTaskClient(api_key="test-key", session=session)

        with patch("oomol_cloud_task.client.time.monotonic", side_effect=[0.0, 0.0, 61.0 / 1000.0, 61.0 / 1000.0]):
            with self.assertRaises(TimeoutError) as ctx:
                client.await_result("task-1", interval_ms=1, timeout_ms=60)

        self.assertEqual(
            str(ctx.exception),
            "Task polling timeout after 1 minutes. Last polling request error: server busy",
        )

    @patch("oomol_cloud_task.client.time.sleep", return_value=None)
    def test_create_and_wait_returns_named_tuple_response(self, _sleep):
        session = FakeSession(
            post_responses=[FakeResponse(json_data={"taskID": "task-1"})],
            get_responses=[FakeResponse(json_data={"status": "success", "resultURL": None, "resultData": []})],
        )
        client = OomolTaskClient(api_key="test-key", session=session)

        response = client.create_and_wait(
            {
                "packageName": "@oomol/my-package",
                "packageVersion": "1.0.0",
                "blockName": "main",
            },
            interval_ms=1,
        )

        task_id, result = response
        self.assertEqual(task_id, "task-1")
        self.assertEqual(response.taskID, "task-1")
        self.assertEqual(result["status"], "success")

    @patch("oomol_cloud_task.client.time.sleep", return_value=None)
    def test_upload_file_returns_remote_url(self, _sleep):
        session = FakeSession(
            post_responses=[
                FakeResponse(
                    json_data={
                        "data": {
                            "upload_id": "upload-1",
                            "part_size": 3,
                            "total_parts": 2,
                            "presigned_urls": {
                                "1": "https://upload.example/1",
                                "2": "https://upload.example/2",
                            },
                        }
                    }
                )
            ],
            put_responses=[FakeResponse(), FakeResponse()],
            get_responses=[FakeResponse(json_data={"data": {"url": "https://files.example/output.txt"}})],
        )
        client = OomolTaskClient(api_key="test-key", session=session)

        with tempfile.NamedTemporaryFile(suffix=".txt") as handle:
            handle.write(b"abcdef")
            handle.flush()
            progress_events = []

            url = client.upload_file(handle.name, retries=2, on_progress=progress_events.append)

        self.assertEqual(url, "https://files.example/output.txt")
        self.assertEqual(progress_events[-1], 100)
        self.assertEqual(len(session.calls["put"]), 2)

    def test_api_error_uses_backend_message(self):
        session = FakeSession(get_responses=[FakeResponse(ok=False, status_code=401, json_data={"message": "unauthorized"})])
        client = OomolTaskClient(api_key="test-key", session=session)

        with self.assertRaises(ApiError) as ctx:
            client.get_task_result("task-1")

        self.assertEqual(str(ctx.exception), "unauthorized")
        self.assertEqual(ctx.exception.status, 401)


if __name__ == "__main__":
    unittest.main()
