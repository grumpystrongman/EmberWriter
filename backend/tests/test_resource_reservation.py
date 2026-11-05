"""The production governor serializes competing long operations."""
import asyncio
import unittest
from app.local_resources import reservation, status


class ResourceReservationTests(unittest.IsolatedAsyncioTestCase):
    async def test_sequential_reservations_in_one_process(self):
        order = []
        async def worker(n):
            async with reservation():
                order.append(("enter", n))
                await asyncio.sleep(0.02)
                order.append(("exit", n))
        await asyncio.gather(worker(1), worker(2))
        self.assertEqual(len(order), 4)
        self.assertEqual(order[0][0], "enter")
        self.assertEqual(order[1][0], "exit")
        self.assertEqual(order[2][0], "enter")
        self.assertEqual(order[3][0], "exit")
        self.assertEqual(status()["scope"], "single_machine_cross_process")
