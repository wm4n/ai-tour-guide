"""拍照提問的照片（設計文件第 8 節第 7 點）：只存在主機本機、有保留期限、不入 repo。

照片放在 `~/.buddy-host/photos/`（和其他機密一樣在 repo 外），檔名是不可預測的隨機字串、
只有本人可讀；每次存新照片時順便清掉超過保留期限的舊照片，啟動時也清一次。
Claude 用 `Read` 工具讀這個檔案（`--add-dir` 開放這個資料夾）。
"""

import logging
import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_S = 24 * 3600.0
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
_SIGNATURES = ((b"\xff\xd8\xff", ".jpg"), (b"\x89PNG\r\n\x1a\n", ".png"))
_SUFFIXES = tuple(suffix for _, suffix in _SIGNATURES)


class PhotoRejected(ValueError):
    """不是支援的照片（只收 JPEG、PNG），或太大。"""


class PhotoTooLarge(PhotoRejected):
    pass


class PhotoStore:
    def __init__(
        self,
        directory: Path,
        *,
        retention_s: float = DEFAULT_RETENTION_S,
        max_bytes: int = DEFAULT_MAX_BYTES,
        clock: Callable[[], float] = time.time,
    ):
        self.directory = directory
        self._retention_s = retention_s
        self._max_bytes = max_bytes
        self._clock = clock

    def save(self, data: bytes) -> Path:
        if len(data) > self._max_bytes:
            raise PhotoTooLarge(f"照片太大了（上限 {self._max_bytes // (1024 * 1024)} MB）")
        suffix = next((s for sig, s in _SIGNATURES if data.startswith(sig)), None)
        if suffix is None:
            raise PhotoRejected("只收 JPEG 或 PNG 照片")
        self.purge()
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.directory / f"{uuid.uuid4().hex}{suffix}"
        # 只有本人可讀：先以 0600 建檔再寫入，不留下「先公開再改權限」的空窗
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
        except BaseException:
            path.unlink(missing_ok=True)  # 寫到一半失敗：不留殘缺的照片
            raise
        return path

    def purge(self) -> int:
        """刪掉超過保留期限的照片；回傳刪了幾張。只動自己存的照片（副檔名為 .jpg／.png）。"""
        cutoff = self._clock() - self._retention_s
        removed = 0
        try:
            paths = list(self.directory.iterdir())
        except FileNotFoundError:
            return 0
        except OSError:
            # 清理只是附帶的：列不出來不能讓存照片、問答跟著失敗
            logger.exception("列不出照片資料夾，這次不清理：%s", self.directory)
            return 0
        for path in paths:
            if path.suffix not in _SUFFIXES:
                continue
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                logger.exception("清除過期照片失敗：%s", path)
        return removed
