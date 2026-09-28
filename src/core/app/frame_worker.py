import os
from concurrent.futures import ThreadPoolExecutor, as_completed

MIN_WORKERS = 2


def get_worker_count() -> int:
    """At least 2 workers always, scaled up to the machine's CPU count so
    a batch of 4 frames (or more) gets processed in parallel instead of
    queueing behind a single worker."""
    cpu = os.cpu_count() or 2
    return max(MIN_WORKERS, cpu)


class FrameWorkerPool:
    """A small, reusable thread pool for one AI pipeline (vehicle or face).

    Every frame in an incoming batch is submitted to the pool immediately,
    so as soon as any worker finishes a frame it picks up the next queued
    one automatically (this is how ThreadPoolExecutor's internal queue
    behaves) — no worker sits idle while frames are waiting.
    """

    def __init__(self, name: str, max_workers: int = None):
        self.name = name
        self.max_workers = max_workers or get_worker_count()
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix=name
        )

    def process_batch(self, frames, process_fn):
        """Submits every frame in the batch to the pool at once and blocks
        until the whole batch is done. Returns a list of per-frame results
        (or error dicts, so one bad frame doesn't crash the whole batch)."""
        futures = [self.executor.submit(process_fn, frame) for frame in frames]
        results = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"error": str(exc)})
        return results
