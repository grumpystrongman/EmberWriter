"""Shared process-local slot prevents overlapping heavy local workloads."""
import asyncio
import unittest
from app.local_resources import reservation, status


class WorkloadSerialTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_and_narrator_wait_for_same_slot(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        results = []
        async def heavy_model():
            async with reservation():
                results.append("model-enter")
                entered.set()
                await release.wait()
                results.append("model-exit")
        async def narrator():
            async with reservation():
                results.append("narrator-enter")
        task1 = asyncio.create_task(heavy_model())
        await entered.wait()
        task2 = asyncio.create_task(narrator())
        await asyncio.sleep(.02)
        self.assertEqual(results, ["model-enter"])
        self.assertTrue(status()["busy"])
        self.assertGreaterEqual(status()["waiting"], 1)
        release.set()
        await asyncio.gather(task1, task2)
        self.assertEqual(results, ["model-enter", "model-exit", "narrator-enter"])
        self.assertFalse(status()["busy"])

    async def test_cancelled_waiter_releases_its_queue_position(self):
        active = asyncio.Event()
        release = asyncio.Event()
        async def leader():
            async with reservation():
                active.set()
                await release.wait()
        async def queued():
            async with reservation():
                return True
        task1 = asyncio.create_task(leader())
        await active.wait()
        task2 = asyncio.create_task(queued())
        await asyncio.sleep(.02)
        task2.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task2
        self.assertEqual(status()["waiting"], 0)
        release.set()
        await task1
        self.assertFalse(status()["busy"])
        async with reservation():
            self.assertTrue(status()["busy"])


if __name__ == "__main__":
    unittest.main()
