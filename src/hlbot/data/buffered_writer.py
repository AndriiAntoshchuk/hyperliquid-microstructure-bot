import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from hlbot.data.hyperliquid_ws_paths import output_path


@dataclass(frozen=True)
class WriterMetrics:
    records_written: int
    bytes_written: int
    batches_written: int
    queue_peak: int
    enqueue_wait_seconds: float
    write_seconds: float


def _write_batch(data_dir: Path, records: list[dict]) -> int:
    grouped: dict[Path, list[str]] = defaultdict(list)
    byte_count = 0
    for record in records:
        path = output_path(data_dir, record["coin"], record["channel"], record["local_receive_ns"])
        line = json.dumps(record, separators=(",", ":")) + "\n"
        grouped[path].append(line)
        byte_count += len(line.encode("utf-8"))

    for path, lines in grouped.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.writelines(lines)
            handle.flush()
    return byte_count


class BufferedJSONLWriter:
    _STOP = object()

    def __init__(self, data_dir: str | Path, *, max_queue: int = 4096, batch_size: int = 256,flush_interval: float = 0.25,) -> None:
        if max_queue < 1 or batch_size < 1 or flush_interval <= 0:
            raise ValueError("max_queue and batch_size must be positive; flush_interval > 0")
        self.data_dir = Path(data_dir)
        self.queue: asyncio.Queue[dict | object] = asyncio.Queue(maxsize=max_queue)
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._worker: asyncio.Task | None = None
        self._closed = False
        self._records = 0
        self._bytes = 0
        self._batches = 0
        self._queue_peak = 0
        self._enqueue_wait = 0.0
        self._write_seconds = 0.0

    @property
    def metrics(self) -> WriterMetrics:
        return WriterMetrics(
            self._records, self._bytes, self._batches, self._queue_peak,
            self._enqueue_wait, self._write_seconds,
        )

    @property
    def queued(self) -> int:
        return self.queue.qsize()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def start(self) -> None:
        if self._worker is not None:
            raise RuntimeError("writer already started")
        self._worker = asyncio.create_task(self._run(), name="jsonl-buffered-writer")

    async def _put_or_failure(self, record: dict | object) -> float:
        assert self._worker is not None
        if self._worker.done():
            await self._worker
            raise RuntimeError("writer has stopped")
        try:
            self.queue.put_nowait(record)
            return 0.0
        except asyncio.QueueFull:
            pass

        start = time.perf_counter()
        put_task = asyncio.create_task(self.queue.put(record))
        try:
            done, _ = await asyncio.wait((put_task, self._worker), return_when=asyncio.FIRST_COMPLETED)
            if self._worker in done:
                if not put_task.done():
                    put_task.cancel()
                    await asyncio.gather(put_task, return_exceptions=True)
                await self._worker 
                raise RuntimeError("writer has stopped")
            await put_task
            return time.perf_counter() - start
        finally:
            if not put_task.done():
                put_task.cancel()
                await asyncio.gather(put_task, return_exceptions=True)

    async def write(self, record: dict) -> None:
        if self._closed or self._worker is None:
            raise RuntimeError("writer not running")
        self._enqueue_wait += await self._put_or_failure(record)
        self._queue_peak = max(self._queue_peak, self.queued)

    async def _flush(self, batch: list[dict]) -> None:
        start = time.perf_counter()
        byte_count = await asyncio.to_thread(_write_batch, self.data_dir, batch)
        self._write_seconds += time.perf_counter() - start
        self._bytes += byte_count
        self._records += len(batch)
        self._batches += 1

    async def _run(self) -> None:
        batch: list[dict] = []
        while True:
            try:
                record = await asyncio.wait_for(self.queue.get(), timeout=self.flush_interval)
            except TimeoutError:
                if batch:
                    await self._flush(batch)
                    batch = []
                continue

            if record is self._STOP:
                if batch:
                    await self._flush(batch)
                return

            if not isinstance(record, dict):
                raise TypeError("writer expected a JSON record")
            batch.append(record)
            if len(batch) >= self.batch_size:
                await self._flush(batch)
                batch = []

    async def close(self) -> None:
        if self._closed:
            if self._worker is not None:
                await self._worker
            return
        self._closed = True
        if self._worker is None:
            return
        if not self._worker.done():
            await self._put_or_failure(self._STOP)
        await self._worker
