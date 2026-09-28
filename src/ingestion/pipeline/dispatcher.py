import asyncio
from typing import Dict, Optional

import httpx


class AIDispatcher:
    """
    Sends frame batches to Vehicle AI and Face AI.

    The dispatcher uses bounded queues so that if an AI
    service becomes slow, memory usage does not grow forever.
    """

    def __init__(
        self,
        vehicle_url: str,
        face_url: str,
        queue_size: int = 20
    ):
        self.vehicle_url = vehicle_url
        self.face_url = face_url

        self.vehicle_queue = asyncio.Queue(
            maxsize=queue_size
        )

        self.face_queue = asyncio.Queue(
            maxsize=queue_size
        )

        self.running = False

        self.vehicle_worker_task: Optional[
            asyncio.Task
        ] = None

        self.face_worker_task: Optional[
            asyncio.Task
        ] = None

    async def start(self):
        """
        Start dispatcher workers.
        """

        if self.running:
            return

        self.running = True

        self.vehicle_worker_task = asyncio.create_task(
            self._worker(
                self.vehicle_queue,
                self.vehicle_url,
                "VEHICLE"
            )
        )

        self.face_worker_task = asyncio.create_task(
            self._worker(
                self.face_queue,
                self.face_url,
                "FACE"
            )
        )

        print("[DISPATCHER] Started")

    async def submit_vehicle(self, payload: dict):
        """
        Submit a batch to Vehicle AI.

        Returns False if the queue is full.
        """

        if self.vehicle_queue.full():
            print(
                "[DISPATCHER] Vehicle queue full"
            )
            return False

        await self.vehicle_queue.put(payload)

        return True

    async def submit_face(self, payload: dict):
        """
        Submit a batch to Face AI.

        Returns False if the queue is full.
        """

        if self.face_queue.full():
            print(
                "[DISPATCHER] Face queue full"
            )
            return False

        await self.face_queue.put(payload)

        return True

    async def _worker(
        self,
        queue: asyncio.Queue,
        url: str,
        name: str
    ):
        """
        Continuously take batches from a queue
        and send them to the corresponding AI service.
        """

        async with httpx.AsyncClient(
            timeout=30.0
        ) as client:

            while self.running:

                payload = await queue.get()

                try:
                    await self._send(
                        client,
                        url,
                        payload,
                        name
                    )

                except Exception as error:
                    print(
                        f"[DISPATCHER] "
                        f"{name} error: {error}"
                    )

                finally:
                    queue.task_done()

    async def _send(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: dict,
        name: str
    ):
        """
        Send one batch to an AI service.
        """

        response = await client.post(
            url,
            json=payload
        )

        response.raise_for_status()

        print(
            f"[DISPATCHER] "
            f"{name} batch sent successfully"
        )

    async def stop(self):
        """
        Stop dispatcher workers.
        """

        self.running = False

        tasks = [
            task for task in (
                self.vehicle_worker_task,
                self.face_worker_task,
            )
            if task is not None
        ]

        for task in tasks:
            task.cancel()

        # Await cancellation so each worker's "async with httpx.AsyncClient"
        # actually finishes closing its client before stop() returns --
        # otherwise cleanup races in the background after we've already
        # moved on (stray "Task was destroyed but it is pending" warnings).
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        print("[DISPATCHER] Stopped")