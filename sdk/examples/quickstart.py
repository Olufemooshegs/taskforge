"""End-to-end SDK demo against a running TaskForge instance.

    export TASKFORGE_API_KEY=dev-api-key-change-me
    python examples/quickstart.py
"""

import asyncio
import os

from taskforge import TaskForgeClient


async def main() -> None:
    api_key = os.environ.get("TASKFORGE_API_KEY", "dev-api-key-change-me")
    base_url = os.environ.get("TASKFORGE_URL", "http://localhost:8000")

    async with TaskForgeClient(base_url=base_url, api_key=api_key) as client:
        print(f"Connected. Live: {await client.health_live()}")
        print(f"Ready:   {await client.health_ready()}")

        print("\nQueues:")
        for q in await client.queues():
            print(f"  {q.name}: {q.max_concurrency} concurrency, active={q.is_active}")

        print("\nSubmitting 3 jobs...")
        ids = []
        for i in range(3):
            resp = await client.enqueue(
                task_name="echo",
                payload={"i": i, "msg": f"hello-{i}"},
                queue="default",
                priority="normal",
            )
            ids.append(resp.id)
            print(f"  {resp.id}  status={resp.status}")

        print("\nWaiting for completion...")
        for job_id in ids:
            final = await client.wait_for(job_id, poll_interval=0.3, timeout=30)
            print(f"  {final.id}: {final.status} in {final.attempts} attempt(s)")
            if final.result:
                print(f"    result: {final.result}")


if __name__ == "__main__":
    asyncio.run(main())
