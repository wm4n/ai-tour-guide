"""以 `claude -p`（stream-json）呼叫 Claude Code 的 LLM 介接層。

- 只用 Claude Pro 訂閱：注入 CLAUDE_CODE_OAUTH_TOKEN，並剝除所有 ANTHROPIC_* 憑證，
  避免 `claude` 改走按 token 計費的 API key。
- 每次呼叫都是全新對話（不 resume、不保存 session）；旅程記憶由主機自己管。
- 不使用 --bare（bare 模式不吃 OAuth）。
"""

import asyncio
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from buddy_host.llm.models import (
    ForbiddenModelError,
    LlmRequest,
    LlmResult,
    is_fable,
    resolve_model,
)
from buddy_host.llm.quota import quota_hit, reset_time
from buddy_host.llm.usage_log import UsageLog

logger = logging.getLogger(__name__)

TOKEN_FILENAME = "claude-token"
_STRIPPED_ENV_PREFIXES = ("ANTHROPIC_", "CLAUDE_CODE_USE_")
_STDOUT_LIMIT = 16 * 1024 * 1024


class LlmError(RuntimeError):
    pass


class QuotaExceededError(LlmError):
    def __init__(self, message: str | None = None, resets_at: float | None = None):
        super().__init__(message)
        self.resets_at = resets_at  # epoch 秒；不知道時是 None


@dataclass(frozen=True)
class ClaudeSettings:
    command: tuple[str, ...]
    token_path: Path
    workdir: Path
    usage_log_path: Path
    default_timeout: float = 180.0
    setting_sources: str = "project"

    @classmethod
    def for_home(cls, home: Path, command: tuple[str, ...] = ("claude",), **overrides):
        base = cls(
            command=command,
            token_path=home / TOKEN_FILENAME,
            workdir=home / "workdir",
            usage_log_path=home / "usage.jsonl",
        )
        return replace(base, **overrides)


def _built_in_tools(allowed: tuple[str, ...]) -> list[str]:
    """權限規則（`Read(//路徑/**)`）裡的內建工具名稱；MCP 工具（`mcp__…`）不在 `--tools` 管轄內。"""
    names = (rule.split("(")[0] for rule in allowed)
    return list(dict.fromkeys(name for name in names if not name.startswith("mcp__")))


class _Stream:
    """累積 stream-json 事件。"""

    def __init__(
        self,
        on_text: Callable[[str], None] | None,
        on_tool: Callable[[str], None] | None = None,
    ):
        self.on_text = on_text
        self.on_tool = on_tool
        self._tools_seen: set[str] = set()
        self.partial_text: list[str] = []
        self.assistant_text: list[str] = []
        self.rate_limits: list[dict] = []
        self.init_model: str | None = None
        self.result: dict | None = None
        self.unparsed_lines = 0

    def feed(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            self.init_model = event.get("model")
        elif kind == "stream_event":
            inner = event.get("event", {})
            delta = inner.get("delta", {})
            if delta.get("type") == "text_delta" and delta.get("text"):
                self.partial_text.append(delta["text"])
                self._emit(delta["text"])
            elif inner.get("type") == "content_block_start":
                self._tool_use(inner.get("content_block", {}))
        elif kind == "assistant":
            blocks = event.get("message", {}).get("content", [])
            for block in blocks:
                self._tool_use(block)
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            self.assistant_text.append(text)
            if not self.partial_text:
                self._emit(text)
        elif kind == "rate_limit_event":
            self.rate_limits.append(dict(event.get("rate_limit_info", {})))
        elif kind == "result":
            self.result = event

    def _emit(self, text: str) -> None:
        if text and self.on_text:
            self.on_text(text)

    def _tool_use(self, block: dict) -> None:
        """同一次工具呼叫會先後出現在 content_block_start 與完整的 assistant 訊息：以 id 去重。"""
        if block.get("type") != "tool_use" or not self.on_tool:
            return
        key = block.get("id") or str(block.get("name"))  # 沒有 id 時退而以名稱去重
        if key not in self._tools_seen:
            self._tools_seen.add(key)
            self.on_tool(str(block.get("name", "")))


class ClaudeCliClient:
    def __init__(self, settings: ClaudeSettings):
        self._s = settings
        self._usage = UsageLog(settings.usage_log_path)

    async def run(
        self,
        request: LlmRequest,
        on_text: Callable[[str], None] | None = None,
        on_tool: Callable[[str], None] | None = None,
    ) -> LlmResult:
        model = resolve_model(request.purpose, request.model)
        token = self._read_token()
        stream = _Stream(on_text, on_tool)
        started = time.perf_counter()
        error: str | None = None
        returncode: int | None = None
        stderr = ""
        try:
            returncode, stderr = await self._spawn(request, model, token, stream)
        except TimeoutError:
            error = f"claude 逾時（{request.timeout or self._s.default_timeout} 秒）"

        result = stream.result or {}
        text = result.get("result", "".join(stream.partial_text) or "".join(stream.assistant_text))
        is_error = bool(error) or bool(result.get("is_error")) or stream.result is None
        if error is None and stream.result is None:
            error = f"claude 結束碼 {returncode}，沒有結果。stderr：{stderr[-500:]}"
        elif error is None and result.get("is_error"):
            error = text
        error = self._scrub(error, token) if error else None

        model_usage = result.get("modelUsage", {})
        self._usage.append(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "purpose": request.purpose.value,
                "model_requested": model,
                "modelUsage": model_usage,
                "usage": result.get("usage", {}),
                "reported_cost_usd": result.get("total_cost_usd"),
                "rate_limit_events": stream.rate_limits,
                "unparsed_lines": stream.unparsed_lines,
                "duration_ms": result.get("duration_ms"),
                "wall_ms": round((time.perf_counter() - started) * 1000),
                "is_error": is_error,
                "error": error,
            }
        )

        if any(is_fable(name) for name in model_usage):
            raise ForbiddenModelError(f"modelUsage 出現 Fable：{sorted(model_usage)}")
        if is_error:
            if quota_hit(stream.rate_limits, error):
                raise QuotaExceededError(error, reset_time(stream.rate_limits))
            raise LlmError(error)

        return LlmResult(
            text=text,
            model=next(iter(model_usage), stream.init_model or model),
            usage=result.get("usage", {}),
            model_usage=model_usage,
            rate_limit=stream.rate_limits[-1] if stream.rate_limits else {},
            duration_ms=result.get("duration_ms"),
        )

    def _read_token(self) -> str:
        try:
            token = self._s.token_path.read_text(encoding="utf-8").strip()
        except OSError:
            token = ""
        if not token:
            raise LlmError(
                f"找不到 Claude OAuth token：請執行 `claude setup-token`，"
                f"把結果存到 {self._s.token_path}（{TOKEN_FILENAME}）"
            )
        return token

    def _env(self, token: str) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith(_STRIPPED_ENV_PREFIXES)}
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        return env

    def _args(self, request: LlmRequest, model: str) -> list[str]:
        args = [
            "-p",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--no-session-persistence",
            "--model", model,
            "--setting-sources", self._s.setting_sources,
            "--disable-slash-commands",
            "--strict-mcp-config",
        ]  # fmt: skip
        if request.mcp_config:
            args += ["--mcp-config", str(request.mcp_config)]
        if request.system_prompt:
            args += ["--append-system-prompt", request.system_prompt]
        # 預設的內建工具集連 Bash 都有（唯讀指令免詢問）：只開這次真的需要的，沒有需要就全關（""）。
        # 網頁、照片裡的文字都是第三方內容，可能夾帶指示；工具越少，被牽著走的後果越小。
        args += ["--tools", ",".join(_built_in_tools(request.allowed_tools))]
        if request.allowed_tools:
            args += ["--allowedTools", ",".join(request.allowed_tools)]
        for directory in request.add_dirs:
            args += ["--add-dir", str(directory)]
        return args

    async def _spawn(
        self, request: LlmRequest, model: str, token: str, stream: _Stream
    ) -> tuple[int, str]:
        self._s.workdir.mkdir(parents=True, exist_ok=True)
        proc = await asyncio.create_subprocess_exec(
            *self._s.command,
            *self._args(request, model),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env(token),
            cwd=self._s.workdir,
            limit=_STDOUT_LIMIT,
        )
        assert proc.stdin and proc.stdout and proc.stderr  # 以 PIPE 建立，必定存在
        stderr_task = asyncio.create_task(proc.stderr.read())

        async def converse() -> int:
            proc.stdin.write(request.prompt.encode("utf-8"))
            await proc.stdin.drain()
            proc.stdin.close()
            async for raw in proc.stdout:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    stream.feed(json.loads(line))
                except json.JSONDecodeError:
                    stream.unparsed_lines += 1
                    logger.debug("claude stdout 不是 JSON，略過：%.80s", line)
            return await proc.wait()

        try:
            returncode = await asyncio.wait_for(
                converse(), request.timeout or self._s.default_timeout
            )
        except (TimeoutError, asyncio.CancelledError):  # 逾時或呼叫端放棄：行程不能留著繼續耗額度
            proc.kill()
            await proc.wait()
            stderr_task.cancel()
            raise
        stderr = (await stderr_task).decode("utf-8", errors="replace")
        return returncode, self._scrub(stderr, token)

    @staticmethod
    def _scrub(text: str, token: str) -> str:
        return text.replace(token, "***")
