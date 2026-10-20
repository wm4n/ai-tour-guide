import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path


class JsonCache:
    """很小的檔案快取：一個 key 一個 JSON 檔，附寫入時間，過期視為不存在。"""

    def __init__(self, directory: Path, ttl_seconds: float, clock: Callable[[], float] = time.time):
        self._dir = directory
        self._ttl = ttl_seconds
        self._clock = clock

    def _path(self, key: str) -> Path:
        return self._dir / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json")

    def get(self, key: str):
        try:
            entry = json.loads(self._path(key).read_text(encoding="utf-8"))
            if self._clock() - entry["t"] > self._ttl:
                return None
            return entry["v"]
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def set(self, key: str, value) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"t": self._clock(), "v": value}, ensure_ascii=False)
        self._path(key).write_text(payload, encoding="utf-8")
