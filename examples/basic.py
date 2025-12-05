import sys
import os

# Add src to path so we can import the package without installing it
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from oomol_cloud_task import OomolTaskClient, BackoffStrategy

def main():
    client = OomolTaskClient(api_key="YOUR_API_KEY")

    print("Creating task and waiting for result...")
    
    try:
        task_id, result = client.create_and_wait(
            applet_id="54dfbca0-6b2a-4738-bc38-c602981d9be6",
            input_values={
                "input_pdf": "<必填>",
                "output_path": "<必填>",
                "compression_level": None,
                "optimize_images": False,
                "remove_metadata": None,
            },
            interval_ms=2000,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            max_interval_ms=10000,
            on_progress=lambda p, s: print(f"Task in progress: status={s} progress={p or 0}%")
        )
        
        print(f"Task completed: {task_id}")
        print(f"Result: {result}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
