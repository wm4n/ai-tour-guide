"""Unit tests for logging_config: formatters and log_event helper."""

import json
import logging

import pytest

from tour_guide.log_events import LogEvents
from tour_guide.logging_config import _HumanFormatter, _JsonFormatter, log_event, setup_logging


class TestHumanFormatter:
    def _make_record(self, event: str, params: dict, level=logging.INFO) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test", level=level, pathname="", lineno=0,
            msg="", args=(), exc_info=None,
        )
        record.event = event
        record.params = params
        return record

    def test_includes_event_in_brackets(self):
        record = self._make_record("POI_LOADED", {"count": 5})
        output = _HumanFormatter().format(record)
        assert "[POI_LOADED]" in output

    def test_includes_params_as_key_value(self):
        record = self._make_record("POI_LOADED", {"count": 5, "lat": 37.785})
        output = _HumanFormatter().format(record)
        assert "count=5" in output
        assert "lat=37.785" in output

    def test_includes_level_name(self):
        record = self._make_record("POI_LOADED", {}, level=logging.WARNING)
        output = _HumanFormatter().format(record)
        assert "WARNING" in output

    def test_no_params_no_trailing_garbage(self):
        record = self._make_record("SESSION_START", {})
        output = _HumanFormatter().format(record)
        assert "[SESSION_START]" in output
        assert "=" not in output  # no params


class TestJsonFormatter:
    def _make_record(self, event: str, params: dict) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="", args=(), exc_info=None,
        )
        record.event = event
        record.params = params
        return record

    def test_output_is_valid_json(self):
        record = self._make_record("POI_LOADED", {"count": 5})
        output = _JsonFormatter().format(record)
        doc = json.loads(output)
        assert isinstance(doc, dict)

    def test_event_field_present(self):
        record = self._make_record("POI_LOADED", {"count": 5})
        doc = json.loads(_JsonFormatter().format(record))
        assert doc["event"] == "POI_LOADED"

    def test_params_merged_into_top_level(self):
        record = self._make_record("POI_LOADED", {"count": 5, "lat": 37.785})
        doc = json.loads(_JsonFormatter().format(record))
        assert doc["count"] == 5
        assert doc["lat"] == 37.785

    def test_ts_and_level_present(self):
        record = self._make_record("POI_LOADED", {})
        doc = json.loads(_JsonFormatter().format(record))
        assert "ts" in doc
        assert doc["level"] == "INFO"


class TestSetupLogging:
    def test_sets_log_level_on_root_logger(self):
        setup_logging(level="DEBUG", fmt="text")
        assert logging.getLogger().level == logging.DEBUG
        setup_logging(level="INFO", fmt="text")  # reset

    def test_root_logger_has_one_handler_after_repeated_calls(self):
        setup_logging(level="INFO", fmt="text")
        count_after_first = len(logging.getLogger().handlers)
        setup_logging(level="INFO", fmt="text")
        count_after_second = len(logging.getLogger().handlers)
        assert count_after_first == count_after_second  # idempotent, no handler leak


class TestLogEvent:
    def test_log_event_calls_logger_at_info_by_default(self, caplog):
        logger = logging.getLogger("test_log_event")
        with caplog.at_level(logging.INFO, logger="test_log_event"):
            log_event(logger, LogEvents.POI_LOADED, count=5)
        assert any(
            getattr(r, "event", None) == "POI_LOADED"
            for r in caplog.records
        )

    def test_log_event_error_level(self, caplog):
        logger = logging.getLogger("test_log_event_err")
        with caplog.at_level(logging.ERROR, logger="test_log_event_err"):
            log_event(logger, LogEvents.UPSTREAM_FAIL, level="error", service="overpass")
        assert any(r.levelno == logging.ERROR for r in caplog.records)
