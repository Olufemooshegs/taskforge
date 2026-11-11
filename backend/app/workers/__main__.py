import asyncio

from app.workers.runtime import _main

if __name__ == "__main__":
    asyncio.run(_main())
