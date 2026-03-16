import os
import sys

# Add src to path so we can import the package without installing it.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from oomol_cloud_task import BackoffStrategy, OomolTaskClient


def main():
    client = OomolTaskClient(api_key=os.getenv("OOMOL_API_KEY"))

    print("Creating task and waiting for result...")

    try:
        response = client.create_and_wait(
            {
                "packageName": "@oomol/my-package",
                "packageVersion": "1.0.0",
                "blockName": "main",
                "inputValues": {
                    "input1": "value1",
                    "input2": "value2",
                },
            },
            interval_ms=2000,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            max_interval_ms=10000,
            on_progress=lambda p, s: print("Task in progress: status={status} progress={progress}%".format(status=s, progress=p)),
        )

        print("Task completed: {task_id}".format(task_id=response.taskID))
        if response.result["status"] == "success":
            print("Result URL: {result_url}".format(result_url=response.result.get("resultURL")))
            print("Result data: {result_data}".format(result_data=response.result.get("resultData")))

    except Exception as exc:
        print("Error: {error}".format(error=exc))


if __name__ == "__main__":
    main()
