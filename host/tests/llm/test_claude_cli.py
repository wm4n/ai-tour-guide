import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from buddy_host.llm.claude_cli import (
    ClaudeCliClient,
    ClaudeSettings,
    LlmError,
    QuotaExceededError,
)
from buddy_host.llm.models import ForbiddenModelError, LlmRequest, Purpose
from buddy_host.llm.usage_log import UsageLog

FAKE = Path(__file__).parent / "fake_claude.py"
TOKEN = "oauth-token-for-tests"


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / "claude-token").write_text(TOKEN + "\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-must-not-leak")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "auth-must-not-leak")
    return path


def make_client(home: Path, **overrides) -> ClaudeCliClient:
    settings = ClaudeSettings.for_home(home, command=(sys.executable, str(FAKE)), **overrides)
    return ClaudeCliClient(settings)


def request(**kw) -> LlmRequest:
    return LlmRequest(prompt="介紹大稻埕", purpose=kw.pop("purpose", Purpose.WRITE), **kw)


def seen(record: Path) -> dict:
    return json.loads(record.read_text(encoding="utf-8"))


async def test_streams_text_deltas_and_returns_final_text(home, record):
    chunks: list[str] = []

    result = await make_client(home).run(request(), on_text=chunks.append)

    assert chunks == ["你好，", "這是串流回覆。"]
    assert result.text == "你好，這是串流回覆。"
    assert result.model == "claude-sonnet-5-5"
    assert result.rate_limit["status"] == "allowed"


async def test_falls_back_to_assistant_message_when_no_partial_stream(home, record, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "no_partial")
    chunks: list[str] = []

    result = await make_client(home).run(request(), on_text=chunks.append)

    assert result.text == "你好，這是完整回覆。"
    assert chunks == ["你好，這是完整回覆。"]


async def test_uses_oauth_token_and_strips_api_key_credentials(home, record):
    await make_client(home).run(request())

    env = seen(record)["env"]
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == TOKEN
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env


async def test_arguments_are_headless_fresh_and_never_bare(home, record):
    await make_client(home).run(request(purpose=Purpose.JUDGE))

    argv = seen(record)["argv"]
    assert argv[0] == "-p"
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert argv[argv.index("--model") + 1] == "haiku"
    assert "--no-session-persistence" in argv
    assert "--include-partial-messages" in argv
    for forbidden in ("--bare", "--resume", "-r", "--continue", "-c", "--session-id"):
        assert forbidden not in argv


async def test_prompt_goes_through_stdin_not_argv(home, record):
    await make_client(home).run(request())

    data = seen(record)
    assert data["stdin"] == "介紹大稻埕"
    assert "介紹大稻埕" not in data["argv"]


async def test_runs_in_an_isolated_working_directory(home, record):
    await make_client(home).run(request())

    assert Path(seen(record)["cwd"]).resolve() == (home / "workdir").resolve()


async def test_optional_arguments_are_passed(home, record, tmp_path):
    mcp = tmp_path / "mcp.json"
    mcp.write_text("{}")

    await make_client(home).run(
        request(system_prompt="你是好友", mcp_config=mcp, allowed_tools=("Read", "mcp__places__*"))
    )

    argv = seen(record)["argv"]
    assert argv[argv.index("--append-system-prompt") + 1] == "你是好友"
    assert argv[argv.index("--mcp-config") + 1] == str(mcp)
    assert "--strict-mcp-config" in argv
    assert argv[argv.index("--allowedTools") + 1] == "Read,mcp__places__*"


async def test_fable_is_refused_before_spawning(home, record):
    with pytest.raises(ForbiddenModelError):
        await make_client(home).run(request(model="claude-fable-5-1"))

    assert not record.exists()


async def test_fable_showing_up_in_model_usage_is_flagged_and_logged(home, record, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "fable")
    client = make_client(home)

    with pytest.raises(ForbiddenModelError, match="modelUsage"):
        await client.run(request())

    assert "fable" in json.dumps(UsageLog(home / "usage.jsonl").read_all()[0]["modelUsage"])


async def test_missing_token_fails_before_spawning(tmp_path, record):
    with pytest.raises(LlmError, match="claude-token"):
        await make_client(tmp_path).run(request())

    assert not record.exists()


async def test_every_call_writes_a_usage_record(home, record):
    await make_client(home).run(request(purpose=Purpose.QA))

    [entry] = UsageLog(home / "usage.jsonl").read_all()
    assert entry["purpose"] == "qa"
    assert entry["model_requested"] == "sonnet"
    assert entry["modelUsage"]["claude-sonnet-5-5"]["outputTokens"] == 34
    assert entry["rate_limit_events"][0]["status"] == "allowed"
    assert entry["rate_limit_events"][0]["resetsAt"] == 1760900000
    assert entry["rate_limit_events"][0]["unifiedWindows"]["five_hour"]["utilization"] == 0.42
    assert entry["is_error"] is False
    assert entry["duration_ms"] == 1234
    assert entry["timestamp"]
    assert TOKEN not in json.dumps(entry)


async def test_quota_rejection_raises_and_is_still_logged(home, record, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "quota")

    with pytest.raises(QuotaExceededError):
        await make_client(home).run(request())

    [entry] = UsageLog(home / "usage.jsonl").read_all()
    assert entry["is_error"] is True
    assert entry["rate_limit_events"][0]["status"] == "rejected"


async def test_quota_rejection_carries_when_the_limit_resets(home, record, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "quota")

    with pytest.raises(QuotaExceededError) as exc:
        await make_client(home).run(request())

    assert exc.value.resets_at == 1760900000


async def test_quota_error_text_alone_is_recognised_without_a_reset_time(home, record, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "quota_text")

    with pytest.raises(QuotaExceededError) as exc:
        await make_client(home).run(request())

    assert exc.value.resets_at is None


async def test_nonzero_exit_is_an_error_and_never_leaks_the_token(home, record, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "crash")

    with pytest.raises(LlmError) as exc:
        await make_client(home).run(request())

    assert TOKEN not in str(exc.value)
    assert "boom" in str(exc.value)
    assert TOKEN not in (home / "usage.jsonl").read_text(encoding="utf-8")


async def test_timeout_kills_the_process(home, record, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")

    with pytest.raises(LlmError, match="逾時"):
        await make_client(home).run(request(timeout=0.5))


async def test_cancelling_the_call_kills_the_process(home, record, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")
    task = asyncio.create_task(make_client(home).run(request(timeout=30)))
    for _ in range(100):  # 等假的 claude 起來、寫下自己的 pid
        if record.exists() and record.read_text(encoding="utf-8"):
            break
        await asyncio.sleep(0.05)
    pid = seen(record)["pid"]

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    with pytest.raises(ProcessLookupError):  # 行程已經被殺掉、也收掉了
        os.kill(pid, 0)


async def test_each_call_is_independent(home, record):
    client = make_client(home)

    await client.run(request())
    first = seen(record)["argv"]
    await client.run(request())

    assert seen(record)["argv"] == first
    assert len(UsageLog(home / "usage.jsonl").read_all()) == 2


async def test_unparseable_stdout_lines_are_counted_in_the_usage_record(home, record, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "noisy")

    result = await make_client(home).run(request())

    assert result.text == "你好，這是串流回覆。"
    [entry] = UsageLog(home / "usage.jsonl").read_all()
    assert entry["unparsed_lines"] == 2


async def test_reports_each_tool_use_once_even_though_it_appears_twice_in_the_stream(
    home, record, monkeypatch
):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "tool")
    tools: list[str] = []

    result = await make_client(home).run(request(), on_tool=tools.append)

    assert tools == ["WebSearch", "Read"]
    assert result.text == "你好，這是串流回覆。"


async def test_on_tool_is_optional(home, record, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "tool")

    result = await make_client(home).run(request())

    assert result.text


async def test_only_the_built_in_tools_a_request_needs_are_available(home, record):
    await make_client(home).run(
        request(allowed_tools=("Read(//home/x/photos/**)", "WebSearch", "mcp__places__*", "Read"))
    )

    argv = seen(record)["argv"]
    # 權限規則的括號與 MCP 工具名不屬於內建工具；重複的只留一個
    assert argv[argv.index("--tools") + 1] == "Read,WebSearch"
    assert argv[argv.index("--allowedTools") + 1] == (
        "Read(//home/x/photos/**),WebSearch,mcp__places__*,Read"
    )


async def test_a_request_without_tools_gets_no_built_in_tools_at_all(home, record):
    await make_client(home).run(request())

    argv = seen(record)["argv"]
    # 預設的工具集連 Bash 都有（唯讀指令不用詢問）：沒有需要就一個都不給
    assert argv[argv.index("--tools") + 1] == ""


async def test_an_mcp_only_request_gets_no_built_in_tools(home, record):
    await make_client(home).run(request(allowed_tools=("mcp__probe__probe_nonce",)))

    argv = seen(record)["argv"]
    assert argv[argv.index("--tools") + 1] == ""
