"""Tests for the JSON logging set up by ``configure_telemetry``."""

from __future__ import annotations

import io
import json
import logging

import pytest
from opencomplai_core.telemetry import JsonFormatter, configure_telemetry

TELEMETRY_LOGGER = "opencomplai_core.telemetry"


@pytest.fixture(autouse=True)
def _restore_root_logging(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    # A service module imported earlier in the run may already have installed one.
    root.handlers[:] = [
        h for h in handlers if not isinstance(h.formatter, JsonFormatter)
    ]
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def _records(capsys) -> list[dict]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def _configure_quietly(capsys, service_name: str = "test-service") -> None:
    configure_telemetry(service_name)
    capsys.readouterr()  # drop anything the OTel SDK logged while starting up


def test_record_is_one_parseable_json_line_on_stdout(capsys):
    _configure_quietly(capsys)

    logging.getLogger("svc.module").warning("hello %s", "world")

    out = capsys.readouterr().out
    assert len(out.splitlines()) == 1
    record = json.loads(out)
    assert record["level"] == "WARNING"
    assert record["logger"] == "svc.module"
    assert record["service"] == "test-service"
    assert record["msg"] == "hello world"
    assert record["ts"]
    assert "exc_info" not in record
    assert "trace_id" not in record


def test_message_with_newline_stays_on_one_line(capsys):
    _configure_quietly(capsys)

    logging.getLogger("svc").warning("first\nsecond")

    out = capsys.readouterr().out
    assert len(out.splitlines()) == 1
    assert json.loads(out)["msg"] == "first\nsecond"


def test_exception_includes_exc_info(capsys):
    _configure_quietly(capsys)

    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("svc").exception("failed")

    [record] = _records(capsys)
    assert record["level"] == "ERROR"
    assert "ValueError: boom" in record["exc_info"]


def test_otel_service_name_overrides_service_field(capsys, monkeypatch):
    monkeypatch.setenv("OTEL_SERVICE_NAME", "from-env")
    _configure_quietly(capsys)

    logging.getLogger("svc").warning("hi")

    [record] = _records(capsys)
    assert record["service"] == "from-env"


@pytest.mark.parametrize("value", ["bogus", ""])
def test_unusable_log_level_falls_back_to_info_with_one_warning(
    capsys, monkeypatch, value
):
    monkeypatch.setenv("LOG_LEVEL", value)

    configure_telemetry("test-service")

    assert logging.getLogger().level == logging.INFO
    warnings = [r for r in _records(capsys) if r["logger"] == TELEMETRY_LOGGER]
    assert len(warnings) == 1
    assert warnings[0]["level"] == "WARNING"
    assert "LOG_LEVEL" in warnings[0]["msg"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10", logging.DEBUG),
        ("warn", logging.WARNING),
        ("WARNING", logging.WARNING),
        (" debug ", logging.DEBUG),
    ],
)
def test_usable_log_level_is_applied_without_warning(
    capsys, monkeypatch, value, expected
):
    monkeypatch.setenv("LOG_LEVEL", value)

    configure_telemetry("test-service")

    assert logging.getLogger().level == expected
    assert not [r for r in _records(capsys) if r["logger"] == TELEMETRY_LOGGER]


def test_repeated_calls_leave_one_json_handler():
    for _ in range(3):
        configure_telemetry("test-service")

    root = logging.getLogger()
    assert sum(isinstance(h.formatter, JsonFormatter) for h in root.handlers) == 1


def test_existing_root_handler_survives():
    stream = io.StringIO()
    foreign = logging.StreamHandler(stream)
    root = logging.getLogger()
    root.addHandler(foreign)

    configure_telemetry("test-service")

    assert foreign in root.handlers
    logging.getLogger("svc").warning("still here")
    assert "still here" in stream.getvalue()


def test_trace_id_is_added_inside_an_active_span(capsys):
    sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
    tracer = sdk_trace.TracerProvider().get_tracer("test")
    _configure_quietly(capsys)

    with tracer.start_as_current_span("s") as span:
        logging.getLogger("svc").warning("inside")
    expected = f"{span.get_span_context().trace_id:032x}"

    (record,) = _records(capsys)
    assert record["trace_id"] == expected


def test_httpx_request_lines_stay_below_the_log_level(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_telemetry("test-service")

    assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() == logging.WARNING
