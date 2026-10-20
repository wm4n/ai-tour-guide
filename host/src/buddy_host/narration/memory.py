"""記憶體峰值量測。MPS 用統一記憶體，行程 RSS 看不到，所以量系統整體使用量與 swap。"""

import re
import subprocess
import threading
import time
from dataclasses import dataclass


def parse_vm_stat_used_bytes(output: str) -> int:
    match = re.search(r"page size of (\d+) bytes", output)
    if match is None:
        raise ValueError(f"無法解析 vm_stat 輸出：{output[:80]!r}")
    page_size = int(match.group(1))

    def pages(label: str) -> int:
        match = re.search(rf"{label}:\s+(\d+)\.", output)
        return int(match.group(1)) if match else 0

    used = pages("Pages active") + pages("Pages wired down") + pages("Pages occupied by compressor")
    return used * page_size


def parse_swap_used_bytes(output: str) -> int:
    match = re.search(r"used = ([\d.]+)([MG])", output)
    if not match:
        return 0
    scale = 1024**2 if match.group(2) == "M" else 1024**3
    return int(float(match.group(1)) * scale)


def _run(*cmd: str) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout


@dataclass
class MemoryReport:
    baseline_used_gb: float
    peak_used_gb: float
    peak_swap_gb: float
    samples: int


class PeakMemorySampler:
    """with 區塊內每秒取樣一次，記錄系統使用量與 swap 的峰值。"""

    def __init__(self, interval: float = 1.0):
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._peak_used = 0
        self._peak_swap = 0
        self._samples = 0
        self._baseline = parse_vm_stat_used_bytes(_run("vm_stat"))

    def _sample(self) -> None:
        self._peak_used = max(self._peak_used, parse_vm_stat_used_bytes(_run("vm_stat")))
        self._peak_swap = max(
            self._peak_swap, parse_swap_used_bytes(_run("sysctl", "-n", "vm.swapusage"))
        )
        self._samples += 1

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._sample()
            time.sleep(self._interval)

    def __enter__(self) -> "PeakMemorySampler":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()
        self._sample()

    def report(self) -> MemoryReport:
        gb = 1024**3
        return MemoryReport(
            round(self._baseline / gb, 2),
            round(self._peak_used / gb, 2),
            round(self._peak_swap / gb, 2),
            self._samples,
        )
