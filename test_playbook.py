import asyncio
import time
from src.api.routers.playbook import ranked_opportunities
async def run():
    try:
        t0 = time.time()
        res = await ranked_opportunities(limit=30, action=None, sector=None)
        print("warning:", res.get("warning"))
        print("time:", time.time() - t0)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(run())
