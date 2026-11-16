"""RuntimeReporter: buffering, batching, retries and the packaged event schema.

No listening socket: every send goes through an injected transport stub, with an
injected clock and sleep.
"""

import copy
import hashlib
import http.client
import io
import json
import logging
import os
import subprocess
import sys
import threading
import urllib.request
import urllib.response
from datetime import UTC, datetime, timedelta, timezone
from importlib import resources
from pathlib import Path
from stat import S_IMODE

import pytest
from jsonschema import Draft202012Validator
from opencomplai import AgentDecisionLog, RuntimeReporter, runtime
from opencomplai.runtime import FlushResult
from opencomplai_core.signing import canonical_json_bytes
from opencomplai_core.summaries import IncidentClass

# Built from pieces: a quoted key-like literal on a line that says KEY reads as a
# credential to a secret scanner, and this one is a dummy.
KEY = "ock_" + "test-SECRET-key-123"
URL = "https://events.example.test"
MARKER = "MARKER-tool-input-7f3a91c2"
SCHEMA = json.loads(
    resources.files("opencomplai")
    .joinpath("data/runtime_event.schema.json")
    .read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA)
_NOW = datetime(2026, 11, 9, 12, 0, 0, 123456, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("OPENCOMPLAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENCOMPLAI_DASHBOARD_URL", raising=False)


class Stub:
    """Transport stub: returns the given statuses in order, the last one repeating.
    An exception in the list is raised instead of returned."""

    def __init__(self, *statuses):
        self.statuses = list(statuses) or [202]
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, dict(headers), body, timeout))
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        if isinstance(status, Exception):
            raise status
        return status

    def batches(self):
        return [json.loads(body) for _, _, body, _ in self.calls]


def make(tmp_path, *statuses, **kwargs):
    stub = Stub(*statuses)
    sleeps = []
    options = {
        "api_key": KEY,
        "base_url": URL,
        "buffer_path": tmp_path / "buf.jsonl",
        "transport": stub,
        "clock": lambda: _NOW,
        "sleep": sleeps.append,
        **kwargs,
    }
    reporter = RuntimeReporter("support-bot", **options)
    return reporter, stub, sleeps


def buffered(tmp_path, name="buf.jsonl"):
    path = tmp_path / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def batch_of(*events):
    return {"schema_version": "1", "system_id": "support-bot", "events": list(events)}


def one_of_each(reporter):
    reporter.decision("a1", "search", "success", {"q": 1}, mandate_ref="M-1")
    reporter.decision("a1", "search", "blocked", {"q": 2})
    reporter.out_of_mandate("a1", "delete_row", {"id": 3}, mandate_ref="M-1")
    reporter.metric("latency_ms", 182.5, unit="ms")
    reporter.metric("queue.depth", 4)
    reporter.incident("high", "health_harm")
    reporter.incident("low", IncidentClass.UNCLASSIFIED)


# -- the packaged schema -------------------------------------------------------


def test_schema_is_packaged_and_valid():
    assert (
        resources.files("opencomplai")
        .joinpath("data/runtime_event.schema.json")
        .is_file()
    )
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$id"] == "https://schemas.opencomplai.dev/runtime_event_batch/v1"


def test_every_kind_builds_an_event_that_validates(tmp_path):
    reporter, _, _ = make(tmp_path)
    one_of_each(reporter)
    events = buffered(tmp_path)
    assert {e["kind"] for e in events} == {
        "decision_log",
        "out_of_mandate",
        "metric",
        "incident",
    }
    assert len(events) == 7
    VALIDATOR.validate(batch_of(*events))
    assert events[0]["occurred_at"] == "2026-11-09T12:00:00.123456Z"
    assert len({e["event_id"] for e in events}) == 7


def test_incident_class_enum_matches_the_core_enum():
    incident = SCHEMA["$defs"]["IncidentEvent"]["properties"]["incident_class"]["enum"]
    assert set(incident) == {c.value for c in IncidentClass}


def _valid_decision(reporter_dir):
    reporter = RuntimeReporter(
        "s", buffer_path=reporter_dir / "b.jsonl", clock=lambda: _NOW
    )
    reporter.decision("a", "t", "success", 1)
    return buffered(reporter_dir, "b.jsonl")[0]


def test_schema_rejects_bad_batches(tmp_path):
    event = _valid_decision(tmp_path)
    VALIDATOR.validate(batch_of(event))

    def rejects(batch):
        assert not VALIDATOR.is_valid(batch)

    rejects(batch_of({**event, "intent": "why"}))  # an extra key
    rejects(batch_of({**event, "input_hash": "sha256:abc"}))  # a bad hash
    rejects(batch_of({**event, "input_hash": event["input_hash"] + "\n"}))
    rejects(batch_of({**event, "event_id": event["event_id"] + "\n"}))
    rejects(batch_of({**event, "kind": "free_text"}))  # an unknown kind
    rejects(batch_of({**event, "outcome": "maybe"}))
    rejects(batch_of({**event, "tool": "bad\ntool"}))
    rejects(batch_of({**event, "occurred_at": "2026-11-09 12:00:00"}))
    rejects(batch_of(*[event] * 101))  # more than 100 events
    rejects(batch_of())  # no events
    rejects({**batch_of(event), "schema_version": "2"})
    rejects({**batch_of(event), "extra": 1})
    rejects({**batch_of(event), "system_id": "bad\x00id"})
    rejects({**batch_of(event), "sdk_version": "not a version"})
    incomplete = copy.deepcopy(event)
    del incomplete["agent_id"]
    rejects(batch_of(incomplete))
    VALIDATOR.validate(batch_of(*[event] * 100))
    VALIDATOR.validate({**batch_of(event), "sdk_version": "0.15.0"})
    VALIDATOR.validate(batch_of({**event, "mandate_ref": None}))


def test_schema_rejects_a_trailing_newline_and_out_of_range_values(tmp_path):
    reporter, _, _ = make(tmp_path)
    reporter.metric("m", 1, unit="ms")
    metric = buffered(tmp_path)[0]
    VALIDATOR.validate({**batch_of(metric), "sdk_version": "0.15.0"})
    # Python's jsonschema uses re.search, where "$" also matches before a final newline
    for key in ("name", "unit", "occurred_at"):
        assert not VALIDATOR.is_valid(batch_of({**metric, key: metric[key] + "\n"}))
    assert not VALIDATOR.is_valid({**batch_of(metric), "sdk_version": "0.15.0\n"})
    # json.loads turns an overflowing literal into infinity
    for value in (json.loads("1e999"), json.loads("-1e999"), 1e16, -1e16):
        assert not VALIDATOR.is_valid(batch_of({**metric, "value": value}))
    for value in (0, 1e15, -1e15):
        VALIDATOR.validate(batch_of({**metric, "value": value}))


# -- recording -----------------------------------------------------------------


def test_tool_input_never_reaches_the_buffer_or_the_post_body(tmp_path):
    reporter, stub, _ = make(tmp_path)
    reporter.decision("a1", "search", "success", {"q": MARKER})
    reporter.out_of_mandate("a1", "search", MARKER)
    assert MARKER not in (tmp_path / "buf.jsonl").read_text(encoding="utf-8")
    assert reporter.flush().sent == 2
    assert MARKER not in stub.calls[0][2].decode("utf-8")


def test_input_hash_matches_the_agent_log_hash(tmp_path):
    reporter, _, _ = make(tmp_path)
    payload = {"order_id": 1042, "amount": 19.99}
    reporter.decision("a1", "refund", "success", payload)
    log = AgentDecisionLog(tmp_path / "agent.jsonl")
    entry = log.record(
        agent_id="a1", tool="refund", intent="x", tool_input=payload, outcome="success"
    )
    digest = hashlib.sha256(canonical_json_bytes({"input": payload})).hexdigest()
    assert buffered(tmp_path)[0]["input_hash"] == entry["input_hash"]
    assert entry["input_hash"] == "sha256:" + digest


def test_clock_is_converted_to_utc(tmp_path):
    local = datetime(2026, 11, 9, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    reporter, _, _ = make(tmp_path, clock=lambda: local)
    reporter.metric("m", 1)
    assert buffered(tmp_path)[0]["occurred_at"] == "2026-11-09T12:00:00.000000Z"


@pytest.mark.parametrize(
    "call",
    [
        lambda r: r.decision("", "t", "success", 1),
        lambda r: r.decision("a", "t" * 129, "success", 1),
        lambda r: r.decision("a", "t\n", "success", 1),
        lambda r: r.decision("a", "t", "maybe", 1),
        lambda r: r.decision("a", "t", "success", 1, mandate_ref=""),
        lambda r: r.out_of_mandate("a\x00", "t", 1),
        lambda r: r.metric("Bad-Name", 1),
        lambda r: r.metric("m", float("nan")),
        lambda r: r.metric("m", float("inf")),
        lambda r: r.metric("m", 10**400),
        lambda r: r.metric("m", 1e16),
        lambda r: r.metric("m", -(10**16)),
        lambda r: r.metric("m", True),
        lambda r: r.metric("m", "5"),
        lambda r: r.metric("m", 1, unit="Milliseconds"),
        lambda r: r.incident("urgent", "death"),
        lambda r: r.incident("low", "made_up"),
    ],
)
def test_bad_arguments_raise_and_record_nothing(tmp_path, call):
    reporter, _, _ = make(tmp_path)
    with pytest.raises(ValueError):  # noqa: PT011 - every case is a ValueError
        call(reporter)
    assert reporter.stats()["buffered"] == 0
    assert buffered(tmp_path) == []


def test_metric_values_at_the_bounds_are_accepted(tmp_path):
    reporter, _, _ = make(tmp_path)
    reporter.metric("m", 1e15)
    reporter.metric("m", -(10**15))
    VALIDATOR.validate(batch_of(*buffered(tmp_path)))


def test_recording_makes_no_network_call(tmp_path):
    reporter, stub, sleeps = make(tmp_path)
    one_of_each(reporter)
    assert stub.calls == []
    assert sleeps == []


def test_buffer_overflow_counts_dropped_with_one_warning(tmp_path, caplog):
    reporter, _, _ = make(tmp_path, max_buffered=3)
    with caplog.at_level(logging.WARNING, logger="opencomplai.runtime"):
        for i in range(8):
            reporter.metric("m", i)
    assert len(buffered(tmp_path)) == 3
    assert reporter.stats()["dropped"] == 5
    assert reporter.stats()["buffered"] == 3
    assert len([r for r in caplog.records if r.name == "opencomplai.runtime"]) == 1


def test_the_full_buffer_warning_is_logged_outside_the_lock(tmp_path):
    reporter, _, _ = make(tmp_path, max_buffered=1)
    seen = []

    class Handler(logging.Handler):
        def emit(self, record):
            seen.append(reporter.stats()["dropped"])  # takes the reporter's lock

    logger = logging.getLogger("opencomplai.runtime")
    handler = Handler()
    logger.addHandler(handler)
    try:
        worker = threading.Thread(
            target=lambda: [reporter.metric("m", i) for i in range(3)], daemon=True
        )
        worker.start()
        worker.join(timeout=5)
        assert not worker.is_alive(), "recording deadlocked on its own warning"
    finally:
        logger.removeHandler(handler)
    assert seen == [1]
    assert reporter.stats()["dropped"] == 2


def test_two_reporters_for_different_systems_cannot_share_a_buffer(tmp_path):
    path = tmp_path / "shared.jsonl"
    RuntimeReporter("system-a", buffer_path=path)
    RuntimeReporter("system-a", buffer_path=path)  # the same system is fine
    with pytest.raises(ValueError, match="another system_id"):
        RuntimeReporter("system-b", buffer_path=path)
    RuntimeReporter("system-b", buffer_path=tmp_path / "other.jsonl")


def test_two_threads_recording_give_valid_lines(tmp_path):
    reporter, _, _ = make(tmp_path)

    def work(name):
        for i in range(500):
            reporter.metric(name, i)

    threads = [threading.Thread(target=work, args=(n,)) for n in ("t_a", "t_b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    events = buffered(tmp_path)
    assert len(events) == 1000
    assert len({e["event_id"] for e in events}) == 1000
    for i in range(0, 1000, 100):
        VALIDATOR.validate(batch_of(*events[i : i + 100]))
    assert reporter.stats()["buffered"] == 1000


def test_buffer_survives_a_new_reporter(tmp_path):
    first, _, _ = make(tmp_path)
    first.metric("m", 1)
    second, stub, _ = make(tmp_path)
    assert second.stats()["buffered"] == 1
    assert second.flush().sent == 1
    assert len(stub.calls) == 1


# -- configuration -------------------------------------------------------------


def test_http_url_to_a_remote_host_is_refused(tmp_path):
    with pytest.raises(ValueError):  # noqa: PT011
        RuntimeReporter("s", api_key=KEY, base_url="http://example.com")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8080",
        "http://localhost",
        "http://[::1]:8080",
        "https://events.example.test/api/",
    ],
)
def test_https_and_local_http_urls_are_accepted(tmp_path, url):
    RuntimeReporter("s", api_key=KEY, base_url=url, buffer_path=tmp_path / "b.jsonl")


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "https://user:pw@example.com",
        "https://example.com?x=1",
        "https://example.com#frag",
        "https://example.com:notaport",
        "https://exa mple.com",
        "https:///nohost",
        "example.com",
    ],
)
def test_malformed_urls_are_refused(tmp_path, url):
    with pytest.raises(ValueError, match="base_url") as info:
        RuntimeReporter("s", api_key=KEY, base_url=url)
    assert KEY not in str(info.value)


@pytest.mark.parametrize("key", ["has space", "tab\there", "new\nline", "café"])
def test_a_malformed_key_is_refused_without_echoing_it(key):
    with pytest.raises(ValueError, match="api_key") as info:
        RuntimeReporter("s", api_key=key, base_url=URL)
    assert key not in str(info.value)


@pytest.mark.parametrize("size", [0, 101, -1])
def test_batch_size_must_be_1_to_100(size):
    with pytest.raises(ValueError):  # noqa: PT011
        RuntimeReporter("s", batch_size=size)


@pytest.mark.parametrize("system_id", ["", "x" * 201, "a\nb"])
def test_system_id_is_validated(system_id):
    with pytest.raises(ValueError):  # noqa: PT011
        RuntimeReporter(system_id)


def test_settings_default_to_the_push_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_API_KEY", KEY)
    monkeypatch.setenv("OPENCOMPLAI_DASHBOARD_URL", URL + "/")
    stub = Stub(202)
    reporter = RuntimeReporter(
        "support-bot", buffer_path=tmp_path / "b.jsonl", transport=stub
    )
    reporter.metric("m", 1)
    assert reporter.flush() == FlushResult(1, 0, 0, None)
    url, headers, body, timeout = stub.calls[0]
    assert url == URL + "/v1/runtime-events"
    assert headers["Authorization"] == f"Bearer {KEY}"
    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"].startswith("opencomplai-sdk/")
    assert timeout == 10.0
    sent = json.loads(body)
    assert sent["schema_version"] == "1"
    assert sent["system_id"] == "support-bot"
    VALIDATOR.validate(sent)


def test_local_only_mode_buffers_and_makes_no_transport_call(tmp_path):
    stub = Stub(202)
    reporter = RuntimeReporter("s", buffer_path=tmp_path / "b.jsonl", transport=stub)
    reporter.metric("m", 1)
    assert reporter.stats()["configured"] is False
    assert reporter.flush() == FlushResult(0, 0, 1, "not_configured")
    assert stub.calls == []
    assert len(buffered(tmp_path, "b.jsonl")) == 1
    half = RuntimeReporter(
        "s", api_key=KEY, buffer_path=tmp_path / "b.jsonl", transport=stub
    )
    assert half.flush().error == "not_configured"
    assert stub.calls == []


# -- sending -------------------------------------------------------------------


def test_batching_250_events_gives_3_posts_and_an_empty_buffer(tmp_path):
    reporter, stub, sleeps = make(tmp_path, batch_size=100)
    for i in range(250):
        reporter.metric("m", i)
    assert reporter.flush() == FlushResult(250, 0, 0, None)
    assert [len(b["events"]) for b in stub.batches()] == [100, 100, 50]
    for batch in stub.batches():
        VALIDATOR.validate(batch)
    assert buffered(tmp_path) == []
    assert reporter.stats()["buffered"] == 0
    assert sleeps == []
    assert reporter.flush() == FlushResult(0, 0, 0, None)
    assert len(stub.calls) == 3


def test_503_then_202_retries_once_with_the_base_backoff(tmp_path):
    reporter, stub, sleeps = make(tmp_path, 503, 202)
    reporter.metric("m", 1)
    assert reporter.flush() == FlushResult(1, 0, 0, None)
    assert len(stub.calls) == 2
    assert sleeps == [0.5]
    assert stub.batches()[0] == stub.batches()[1]


def test_repeated_503_gives_unreachable_and_keeps_the_events(tmp_path):
    reporter, stub, sleeps = make(tmp_path, 503)
    reporter.metric("m", 1)
    reporter.metric("m", 2)
    assert reporter.flush() == FlushResult(0, 0, 2, "unreachable")
    assert len(stub.calls) == 4  # the first try and max_retries=3 retries
    assert sleeps == [0.5, 1.0, 2.0]
    assert len(buffered(tmp_path)) == 2


@pytest.mark.parametrize("status", [408, 429, 500, 502, 302, 404, 405, 410])
def test_retryable_statuses_end_as_unreachable(tmp_path, status):
    reporter, stub, _ = make(tmp_path, status, max_retries=1)
    reporter.metric("m", 1)
    assert reporter.flush() == FlushResult(0, 0, 1, "unreachable")
    assert len(stub.calls) == 2


def test_a_network_error_is_retried_and_never_echoed(tmp_path, caplog):
    boom = OSError(f"connection to {URL} failed for {KEY}")
    reporter, stub, sleeps = make(tmp_path, boom, 202)
    reporter.metric("m", 1)
    assert reporter.flush() == FlushResult(1, 0, 0, None)
    assert sleeps == [0.5]
    reporter.metric("m", 2)
    stub.statuses = [boom]
    with caplog.at_level(logging.DEBUG):
        result = reporter.flush()
    assert result.error == "unreachable"
    assert KEY not in result.error
    assert KEY not in caplog.text


@pytest.mark.parametrize("status", [401, 403])
def test_unauthorized_stops_at_once_and_keeps_the_events(tmp_path, status):
    reporter, stub, sleeps = make(tmp_path, status, batch_size=1)
    reporter.metric("m", 1)
    reporter.metric("m", 2)
    assert reporter.flush() == FlushResult(0, 0, 2, "unauthorized")
    assert len(stub.calls) == 1
    assert sleeps == []
    assert len(buffered(tmp_path)) == 2


@pytest.mark.parametrize("status", [400, 409, 413, 422])
def test_other_4xx_moves_the_batch_to_the_rejected_file(tmp_path, status):
    reporter, stub, sleeps = make(tmp_path, status, 202, batch_size=2)
    for i in range(3):
        reporter.metric("m", i)
    first_two = buffered(tmp_path)[:2]
    # the first batch is refused, the second one goes through
    assert reporter.flush() == FlushResult(1, 2, 0, None)
    assert len(stub.calls) == 2
    assert sleeps == []
    assert buffered(tmp_path) == []
    assert buffered(tmp_path, "buf.jsonl.rejected.jsonl") == first_two
    assert reporter.stats()["buffered"] == 0


def test_the_rejected_file_is_capped_at_max_buffered(tmp_path):
    reporter, _, _ = make(tmp_path, 422, max_buffered=3, batch_size=1)
    for round_ in range(2):
        for i in range(3):
            reporter.metric("m", round_ * 3 + i)
        assert reporter.flush().rejected == 3
    kept = buffered(tmp_path, "buf.jsonl.rejected.jsonl")
    assert [e["value"] for e in kept] == [3, 4, 5]


def test_a_corrupt_buffer_line_is_dropped_not_sent(tmp_path):
    reporter, stub, _ = make(tmp_path)
    reporter.metric("m", 1)
    with (tmp_path / "buf.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{not json\n\n[1,2]\n{"value": NaN}\n')
    fresh, stub, _ = make(tmp_path)
    assert fresh.flush() == FlushResult(1, 3, 0, None)
    assert len(stub.batches()[0]["events"]) == 1
    assert buffered(tmp_path) == []


def test_events_recorded_during_a_flush_are_kept(tmp_path):
    reporter, _, _ = make(tmp_path)
    reporter.metric("m", 1)

    def transport(url, headers, body, timeout):
        reporter.metric("m", 2)  # an application thread records while the POST runs
        return 202

    reporter._transport = transport
    assert reporter.flush() == FlushResult(1, 0, 1, None)
    assert [e["value"] for e in buffered(tmp_path)] == [2]


def test_a_flush_removes_only_the_lines_it_sent(tmp_path):
    reporter, _, _ = make(tmp_path)
    other, _, _ = make(tmp_path)  # a second writer on the same file
    reporter.metric("m", 1)
    reporter.metric("m", 2)
    path = tmp_path / "buf.jsonl"

    def transport(url, headers, body, timeout):
        # meanwhile the other writer sends the first line and records a new one
        rest = path.read_text(encoding="utf-8").splitlines()[1:]
        path.write_text("".join(f"{line}\n" for line in rest), newline="\n")
        other.metric("m", 3)
        return 202

    reporter._transport = transport
    assert reporter.flush() == FlushResult(2, 0, 1, None)
    assert [e["value"] for e in buffered(tmp_path)] == [3]


def test_close_and_the_context_manager_flush_once(tmp_path):
    reporter, stub, _ = make(tmp_path)
    with reporter as same:
        assert same is reporter
        reporter.metric("m", 1)
        assert stub.calls == []
    assert len(stub.calls) == 1
    reporter.metric("m", 2)
    assert reporter.close() == FlushResult(1, 0, 0, None)
    assert len(stub.calls) == 2


def test_an_exception_in_the_with_block_is_not_swallowed(tmp_path):
    reporter, stub, _ = make(tmp_path)
    reporter.metric("m", 1)
    with pytest.raises(RuntimeError), reporter:
        raise RuntimeError("app error")
    assert len(stub.calls) == 1


def test_the_api_key_appears_in_no_file_and_no_error(tmp_path, caplog):
    results = []
    with caplog.at_level(logging.DEBUG):
        for statuses in ([401], [503], [422], [RuntimeError(KEY)], [202]):
            reporter, _, _ = make(tmp_path, *statuses, max_retries=1)
            reporter.metric("m", 1)
            results.append(reporter.flush())
    assert {r.error for r in results} == {"unauthorized", "unreachable", None}
    assert all(KEY not in repr(r) for r in results)
    assert KEY not in caplog.text
    for path in tmp_path.iterdir():
        assert KEY not in path.read_text(encoding="utf-8")


def test_a_buffer_that_cannot_be_read_reports_a_fixed_code(tmp_path):
    reporter, stub, _ = make(tmp_path, buffer_path=tmp_path)  # a directory
    result = reporter.flush()
    assert result.error == "buffer_error"
    assert stub.calls == []


# -- the real sender ------------------------------------------------------------


class _Canned302(urllib.request.HTTPHandler):
    """Answers every request with a redirect, without opening a socket."""

    def __init__(self):
        self.urls = []

    def http_open(self, req):
        self.urls.append(req.full_url)
        headers = http.client.HTTPMessage()
        headers["Location"] = "http://127.0.0.1:2/elsewhere"
        response = urllib.response.addinfourl(
            io.BytesIO(b""), headers, req.full_url, 302
        )
        response.msg = "Found"
        return response


def test_a_redirect_is_not_followed(monkeypatch):
    canned = _Canned302()
    opener = urllib.request.build_opener(runtime._NoRedirectHandler, canned)
    # an http URL goes through the loopback opener, an https one through the other
    monkeypatch.setattr(runtime, "_OPENER", opener)
    monkeypatch.setattr(runtime, "_LOCAL_OPENER", opener)
    url = "http://127.0.0.1:1/v1/runtime-events"
    status = runtime._urllib_transport(
        url, {"Authorization": "Bearer never-replayed"}, b"{}", 1.0
    )
    assert status == 302
    assert canned.urls == [url]  # the Location target was never requested


# -- process-wide state --------------------------------------------------------


def test_importing_the_module_leaves_the_urllib_opener_alone():
    code = (
        "import sys, urllib.request as u\n"
        "before = u._opener\n"
        "import opencomplai.runtime\n"
        "assert u._opener is before, 'the global opener changed'\n"
        "assert 'opencomplai_cli.publish' not in sys.modules\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


# -- request size: UTF-8 bodies, split by bytes ---------------------------------

ASTRAL = chr(0x1F600)  # one character, four bytes in UTF-8, twelve as a JSON escape
LONE_HIGH = chr(0xD800)
LONE_LOW = chr(0xDC00)


def test_100_events_of_astral_labels_stay_under_the_body_limit(tmp_path):
    reporter, stub, _ = make(tmp_path)
    label = ASTRAL * 128
    for i in range(100):
        reporter.decision(label, label, "success", {"i": i}, mandate_ref=label)
    assert reporter.flush() == FlushResult(100, 0, 0, None)
    bodies = [body for _, _, body, _ in stub.calls]
    # as JSON escapes this was 487,072 bytes; the receiver refuses over 262,144
    assert max(len(body) for body in bodies) <= 200_000
    text = bodies[0].decode("utf-8")
    assert ASTRAL * 128 in text
    assert "\\ud83d" not in text
    for batch in stub.batches():
        VALIDATOR.validate(batch)
    assert sum(len(b["events"]) for b in stub.batches()) == 100


def test_a_flush_splits_a_batch_by_size_as_well_as_by_count(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "_MAX_BODY_BYTES", 5_000)
    reporter, stub, _ = make(tmp_path)
    for i in range(100):
        reporter.metric("m", i)
    assert reporter.flush() == FlushResult(100, 0, 0, None)
    assert len(stub.calls) > 1
    assert max(len(body) for _, _, body, _ in stub.calls) <= 5_000
    sent = [event["value"] for batch in stub.batches() for event in batch["events"]]
    assert sent == list(range(100))  # every event once, in order
    assert buffered(tmp_path) == []


def test_an_event_over_the_limit_alone_is_still_sent_on_its_own(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "_MAX_BODY_BYTES", 10)
    reporter, stub, _ = make(tmp_path)
    for i in range(3):
        reporter.metric("m", i)
    assert reporter.flush() == FlushResult(3, 0, 0, None)
    assert [len(b["events"]) for b in stub.batches()] == [1, 1, 1]


# -- text without a UTF-8 form --------------------------------------------------


@pytest.mark.parametrize("bad", [LONE_HIGH, LONE_LOW, "a" + LONE_HIGH + "b"])
@pytest.mark.parametrize(
    "call",
    [
        lambda r, v: r.decision(v, "t", "success", 1),
        lambda r, v: r.decision("a", v, "success", 1),
        lambda r, v: r.decision("a", "t", "success", 1, mandate_ref=v),
        lambda r, v: r.out_of_mandate(v, "t", 1),
    ],
    ids=["agent_id", "tool", "mandate_ref", "out_of_mandate"],
)
def test_an_unpaired_surrogate_is_refused_and_nothing_is_recorded(tmp_path, call, bad):
    reporter, _, _ = make(tmp_path)
    with pytest.raises(ValueError, match="unpaired surrogates"):
        call(reporter, bad)
    assert reporter.stats()["buffered"] == 0


def test_an_unpaired_surrogate_in_the_system_id_is_refused():
    with pytest.raises(ValueError, match="unpaired surrogates"):
        RuntimeReporter("sys" + LONE_HIGH)


def test_astral_characters_are_accepted_in_every_label(tmp_path):
    reporter, stub, _ = make(tmp_path)
    label = "a" + ASTRAL + "b"
    reporter.decision(label, label, "success", 1, mandate_ref=label)
    assert reporter.flush().sent == 1
    assert json.loads(stub.calls[0][2])["events"][0]["agent_id"] == label


def test_the_schema_refuses_an_unpaired_surrogate_and_accepts_astral_text(tmp_path):
    reporter, _, _ = make(tmp_path)
    reporter.decision("a1", "search", "success", 1)
    reporter.metric("m", 1)
    decision, metric = buffered(tmp_path)
    for field in ("agent_id", "tool"):
        VALIDATOR.validate(batch_of({**decision, field: ASTRAL * 128}))
        for bad in (LONE_HIGH, "a" + LONE_LOW):
            assert not VALIDATOR.is_valid(batch_of({**decision, field: bad}))
    assert not VALIDATOR.is_valid(
        {**batch_of(decision), "system_id": "sys" + LONE_HIGH}
    )
    VALIDATOR.validate({**batch_of(decision), "system_id": ASTRAL * 200})
    assert not VALIDATOR.is_valid(batch_of({**metric, "name": "m" + LONE_HIGH}))


# -- hidden and reordering characters, controls above 0x7f ----------------------------

# C1 controls and the characters that hide or reorder text: the first and last of each
# range the custom pack text rules exclude, and a middle one.
_UNSAFE_CODEPOINTS = [
    0x0080,
    0x0085,
    0x009F,
    0x00AD,
    0x034F,
    0x0600,
    0x0605,
    0x061C,
    0x06DD,
    0x070F,
    0x08E2,
    0x115F,
    0x1160,
    0x17B4,
    0x17B5,
    0x180B,
    0x180F,
    0x200B,
    0x200C,
    0x200D,
    0x200E,
    0x200F,
    0x2028,
    0x2029,
    0x202A,
    0x202E,
    0x2060,
    0x2066,
    0x206F,
    0x2800,
    0x3164,
    0xFE00,
    0xFE0F,
    0xFEFF,
    0xFFA0,
    0xFFF9,
    0xFFFB,
    0x13430,
    0x1343F,
    0x1BCA0,
    0x1BCA3,
    0x1D173,
    0x1D17A,
    0xE0000,
    0xE0001,
    0xE0FFF,
]
# Their neighbours and some ordinary text: all stay allowed.
_ORDINARY_CODEPOINTS = [
    0x00A0,
    0x00AC,
    0x00AE,
    0x034E,
    0x05FF,
    0x0606,
    0x06DE,
    0x070E,
    0x08E3,
    0xFFF8,
    0xFFFC,
    0x1342F,
    0x13440,
    0x1BC9F,
    0x1BCA4,
    0x1D172,
    0x1D17B,
    0x0645,  # an Arabic letter
    0x5E9,  # a Hebrew letter
    0x115E,
    0x1161,
    0x17B3,
    0x17B6,
    0x180A,
    0x1810,
    0x2010,
    0x2070,
    0x2801,
    0x3163,
    0x3165,
    0xFE10,
    0xFEFE,
    0xFF9F,
    0xFFA1,
    0xDFFFD,
    0xE1000,
]


def _codepoint_id(codepoint: int) -> str:
    return f"U+{codepoint:04X}"


@pytest.mark.parametrize("codepoint", _UNSAFE_CODEPOINTS, ids=_codepoint_id)
@pytest.mark.parametrize(
    "call",
    [
        lambda r, v: r.decision(v, "t", "success", 1),
        lambda r, v: r.decision("a", v, "success", 1),
        lambda r, v: r.decision("a", "t", "success", 1, mandate_ref=v),
        lambda r, v: r.out_of_mandate(v, "t", 1),
    ],
    ids=["agent_id", "tool", "mandate_ref", "out_of_mandate"],
)
def test_a_hidden_or_reordering_character_is_refused_in_a_label(
    tmp_path, call, codepoint
):
    reporter, _, _ = make(tmp_path)
    with pytest.raises(ValueError, match="hidden or reordering characters"):
        call(reporter, "ab" + chr(codepoint) + "cd")
    assert reporter.stats()["buffered"] == 0


@pytest.mark.parametrize("codepoint", _UNSAFE_CODEPOINTS, ids=_codepoint_id)
def test_a_hidden_or_reordering_character_is_refused_in_the_system_id(codepoint):
    with pytest.raises(ValueError, match="hidden or reordering characters"):
        RuntimeReporter("sys" + chr(codepoint))


@pytest.mark.parametrize("codepoint", _ORDINARY_CODEPOINTS, ids=_codepoint_id)
def test_ordinary_text_next_to_the_excluded_ranges_is_accepted(tmp_path, codepoint):
    reporter, _, _ = make(tmp_path)
    label = "ab" + chr(codepoint) + "cd"
    reporter.decision(label, label, "success", 1, mandate_ref=label)
    assert buffered(tmp_path)[0]["agent_id"] == label
    RuntimeReporter(label, buffer_path=tmp_path / "other.jsonl")


@pytest.mark.parametrize("codepoint", _UNSAFE_CODEPOINTS, ids=_codepoint_id)
def test_the_schema_refuses_the_hidden_characters_too(tmp_path, codepoint):
    reporter, _, _ = make(tmp_path)
    reporter.decision("a1", "search", "success", 1, mandate_ref="M-1")
    decision = buffered(tmp_path)[0]
    bad = "ab" + chr(codepoint) + "cd"
    for field in ("agent_id", "tool", "mandate_ref"):
        assert not VALIDATOR.is_valid(batch_of({**decision, field: bad}))
    assert not VALIDATOR.is_valid({**batch_of(decision), "system_id": bad})


@pytest.mark.parametrize("codepoint", _ORDINARY_CODEPOINTS, ids=_codepoint_id)
def test_the_schema_accepts_ordinary_text_next_to_the_excluded_ranges(
    tmp_path, codepoint
):
    reporter, _, _ = make(tmp_path)
    reporter.decision("a1", "search", "success", 1)
    decision = buffered(tmp_path)[0]
    text = "ab" + chr(codepoint) + "cd"
    VALIDATOR.validate(batch_of({**decision, "agent_id": text, "tool": text}))
    VALIDATOR.validate({**batch_of(decision), "system_id": text})


def test_the_schema_and_the_sdk_exclude_the_same_characters_as_the_pack_text():
    from opencomplai_core.custom_pack import HIDDEN_CHARACTERS

    expected = "[\\x00-\\x1f\\x7f-\\x9f" + HIDDEN_CHARACTERS + "\\ud800-\\udfff]"
    defs = SCHEMA["$defs"]
    for node in (
        SCHEMA["properties"]["system_id"],
        defs["Label"],
        defs["MetricEvent"]["properties"]["name"],
    ):
        assert node["not"]["pattern"] == expected
    # and the SDK's own check is that class minus the surrogates, which `_encodable` tests
    assert runtime._UNSAFE_TEXT.pattern == expected[: -len("\\ud800-\\udfff]")] + "]"


@pytest.mark.parametrize("blank", [" ", "   ", "\t", "\u00a0", "\u3000", " \u2003 "])
def test_a_label_of_only_white_space_is_refused(tmp_path, blank):
    reporter, _, _ = make(tmp_path)
    with pytest.raises(ValueError, match="white space"):
        reporter.decision(blank, "search", "success", 1)
    with pytest.raises(ValueError, match="white space"):
        RuntimeReporter(blank)
    assert reporter.stats()["buffered"] == 0


@pytest.mark.parametrize("blank", [" ", "  ", "\u00a0", "\u3000", " \u2003 "])
def test_the_schema_refuses_a_label_of_only_white_space(tmp_path, blank):
    reporter, _, _ = make(tmp_path)
    reporter.decision("a1", "search", "success", 1, mandate_ref="M-1")
    decision = buffered(tmp_path)[0]
    for field in ("agent_id", "tool", "mandate_ref"):
        assert not VALIDATOR.is_valid(batch_of({**decision, field: blank}))
    assert not VALIDATOR.is_valid({**batch_of(decision), "system_id": blank})


def test_the_schema_file_is_plain_ascii_so_no_invisible_character_hides_in_it():
    raw = (
        resources.files("opencomplai")
        .joinpath("data/runtime_event.schema.json")
        .read_bytes()
    )
    assert raw.isascii()
    assert b"\\udb40\\udc00-\\udb43\\udfff" in raw


@pytest.mark.parametrize(
    "error",
    [RuntimeError("Symlink loop"), OSError("not readable")],
    ids=["runtime-error", "os-error"],
)
def test_a_buffer_path_that_cannot_be_resolved_is_still_claimed(
    tmp_path, monkeypatch, error
):
    def cannot_resolve(self, *args, **kwargs):
        raise error

    monkeypatch.setattr(Path, "resolve", cannot_resolve)
    RuntimeReporter("system-a", buffer_path=tmp_path / "sub" / ".." / "x.jsonl")
    RuntimeReporter("system-a", buffer_path=tmp_path / "x.jsonl")  # the same system
    with pytest.raises(ValueError, match="another system_id"):
        RuntimeReporter("system-b", buffer_path=tmp_path / "x.jsonl")
    with pytest.raises(ValueError, match="another system_id"):
        RuntimeReporter("system-b", buffer_path=tmp_path / "sub" / ".." / "x.jsonl")


def test_a_buffered_event_with_an_unpaired_surrogate_is_dropped_not_sent(tmp_path):
    reporter, _, _ = make(tmp_path)
    reporter.decision("a1", "search", "success", 1)
    reporter.metric("m", 1)
    bad = {**buffered(tmp_path)[0], "agent_id": "a" + LONE_HIGH}
    with (tmp_path / "buf.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(bad) + "\n")  # an older version wrote it escaped
    fresh, stub, _ = make(tmp_path)
    assert fresh.flush() == FlushResult(2, 1, 0, None)
    assert len(stub.batches()[0]["events"]) == 2
    assert buffered(tmp_path) == []


# -- tool input that cannot be hashed ---------------------------------------------


def _deeply_nested(depth: int = 10_000) -> list:
    value: list = []
    for _ in range(depth):
        value = [value]
    return value


def _cycle() -> dict:
    value: dict = {}
    value["self"] = value
    return value


@pytest.mark.parametrize(
    "tool_input",
    [{1: "a", "b": 2}, _deeply_nested(), _cycle()],
    ids=["mixed-keys", "deep", "cycle"],
)
def test_a_tool_input_that_cannot_be_serialised_raises_value_error(
    tmp_path, tool_input
):
    reporter, _, _ = make(tmp_path)
    with pytest.raises(ValueError, match=r"^tool_input cannot be serialised$"):
        reporter.decision("a1", "search", "success", tool_input)
    with pytest.raises(ValueError, match=r"^tool_input cannot be serialised$"):
        reporter.out_of_mandate("a1", "search", tool_input)
    assert reporter.stats()["buffered"] == 0


# -- the buffer claim, permissions and links --------------------------------------


def test_a_buffer_path_with_dot_dot_cannot_bypass_the_one_system_guard(tmp_path):
    (tmp_path / "sub").mkdir()
    RuntimeReporter("system-a", buffer_path=tmp_path / "sub" / ".." / "x.jsonl")
    with pytest.raises(ValueError, match="another system_id"):
        RuntimeReporter("system-b", buffer_path=tmp_path / "x.jsonl")
    with pytest.raises(ValueError, match="another system_id"):
        RuntimeReporter("system-b", buffer_path=tmp_path / "sub" / ".." / "x.jsonl")


def test_buffer_files_are_opened_private_and_without_following_links(
    tmp_path, monkeypatch
):
    nofollow = getattr(os, "O_NOFOLLOW", 0x40000000)
    monkeypatch.setattr(os, "O_NOFOLLOW", nofollow, raising=False)
    real_open, opened = os.open, []

    def spy(path, flags, mode=0o777, **kwargs):
        opened.append((os.fspath(path), flags, mode))
        return real_open(path, flags & ~nofollow, mode, **kwargs)

    made = []
    real_mkdir = Path.mkdir

    def mkdir_spy(self, mode=0o777, parents=False, exist_ok=False):
        made.append(mode)
        return real_mkdir(self, mode, parents, exist_ok)

    monkeypatch.setattr(os, "open", spy)
    monkeypatch.setattr(Path, "mkdir", mkdir_spy)
    reporter, _, _ = make(tmp_path, 422, buffer_path=tmp_path / "state" / "buf.jsonl")
    reporter.metric("m", 1)
    assert reporter.flush().rejected == 1

    assert made == [0o700]
    names = {Path(p).name: (f, m) for p, f, m in opened if "buf.jsonl" in p}
    assert names["buf.jsonl"][0] & nofollow
    assert names["buf.jsonl"][1] == 0o600
    # the replacement files are created by mkstemp: private, and a fresh name each time
    temps = [(p, m) for p, _, m in opened if p.endswith(".tmp")]
    assert temps
    assert all(m == 0o600 and not p.endswith("buf.jsonl.tmp") for p, m in temps)
    assert not list((tmp_path / "state").glob("*.tmp"))  # none left behind


posix_only = pytest.mark.skipif(
    os.name != "posix", reason="POSIX permission bits and symbolic links"
)


@posix_only
def test_the_buffer_folder_and_files_are_private(tmp_path):
    reporter, _, _ = make(tmp_path, 422, buffer_path=tmp_path / "state" / "buf.jsonl")
    reporter.metric("m", 1)
    folder = tmp_path / "state"
    assert S_IMODE(folder.stat().st_mode) == 0o700
    assert S_IMODE((folder / "buf.jsonl").stat().st_mode) == 0o600
    reporter.metric("m", 2)
    assert (
        reporter.flush().rejected == 2
    )  # rewrites the buffer, writes the rejected file
    for name in ("buf.jsonl", "buf.jsonl.rejected.jsonl"):
        assert S_IMODE((folder / name).stat().st_mode) == 0o600
    assert sorted(p.name for p in folder.iterdir()) == [
        "buf.jsonl",
        "buf.jsonl.rejected.jsonl",
    ]


@posix_only
def test_a_symbolic_link_in_place_of_the_buffer_is_not_followed(tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("keep\n", encoding="utf-8")
    (tmp_path / "buf.jsonl").symlink_to(victim)
    reporter, stub, _ = make(tmp_path)
    reporter.metric("m", 1)
    assert reporter.stats()["dropped"] == 1
    assert reporter.flush().error == "buffer_error"
    assert stub.calls == []
    assert victim.read_text(encoding="utf-8") == "keep\n"


# -- loopback http and proxies ------------------------------------------------------


def test_a_loopback_http_url_never_uses_the_default_opener(monkeypatch):
    monkeypatch.setenv("http_proxy", "http://proxy.invalid:3128")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:3128")
    used = []

    class Spy:
        def __init__(self, name):
            self.name = name

        def open(self, request, timeout):
            used.append(self.name)
            raise OSError("no network in tests")

    monkeypatch.setattr(runtime, "_OPENER", Spy("default"))
    monkeypatch.setattr(runtime, "_LOCAL_OPENER", Spy("local"))
    for url in (
        "http://127.0.0.1:8080/v1/runtime-events",
        "http://localhost/v1/runtime-events",
        "http://[::1]:8080/v1/runtime-events",
        "https://events.example.test/v1/runtime-events",
    ):
        with pytest.raises(OSError):  # noqa: PT011
            runtime._urllib_transport(url, {"Authorization": "Bearer k"}, b"{}", 1.0)
    assert used == ["local", "local", "local", "default"]


def test_the_loopback_opener_has_no_proxy_and_still_refuses_redirects(monkeypatch):
    monkeypatch.setenv("http_proxy", "http://proxy.invalid:3128")

    def has_proxy(opener):
        return any(isinstance(h, urllib.request.ProxyHandler) for h in opener.handlers)

    # an opener built the plain way picks the environment's proxy up ...
    assert has_proxy(urllib.request.build_opener(runtime._NoRedirectHandler))
    # ... the loopback one has none, whatever the environment says
    assert not has_proxy(runtime._LOCAL_OPENER)
    assert any(
        isinstance(h, runtime._NoRedirectHandler)
        for h in runtime._LOCAL_OPENER.handlers
    )


# -- bounded flush and close -----------------------------------------------------------


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def slow_receiver(clock, status, calls):
    """A transport that takes its whole timeout to answer."""

    def transport(url, headers, body, timeout):
        calls.append(timeout)
        clock.now += timeout
        return status

    return transport


def test_flush_gives_up_at_the_total_timeout_across_attempts(tmp_path, monkeypatch):
    clock, calls = Clock(), []
    monkeypatch.setattr(runtime, "_monotonic", clock)
    reporter, _, _ = make(
        tmp_path,
        transport=slow_receiver(clock, 503, calls),
        sleep=lambda seconds: setattr(clock, "now", clock.now + seconds),
        total_timeout_s=30,
    )
    reporter.metric("m", 1)
    assert reporter.flush() == FlushResult(0, 0, 1, "unreachable")
    # 10 s, a 0.5 s pause, 10 s, a 1 s pause, then what is left of the 30 s
    assert calls == [10.0, 10.0, 8.5]
    assert clock.now - 1000.0 <= 30.0
    assert len(buffered(tmp_path)) == 1


def test_flush_gives_up_at_the_total_timeout_across_batches(tmp_path, monkeypatch):
    clock, calls = Clock(), []
    monkeypatch.setattr(runtime, "_monotonic", clock)
    reporter, _, _ = make(
        tmp_path,
        transport=slow_receiver(clock, 202, calls),
        batch_size=1,
        total_timeout_s=25,
    )
    for i in range(5):
        reporter.metric("m", i)
    assert reporter.flush() == FlushResult(3, 0, 2, "unreachable")
    assert calls == [10.0, 10.0, 5.0]  # the last request gets only what is left
    assert [e["value"] for e in buffered(tmp_path)] == [3, 4]
    assert clock.now - 1000.0 <= 25.0


def test_close_makes_a_single_attempt(tmp_path):
    reporter, stub, sleeps = make(tmp_path, 503)
    reporter.metric("m", 1)
    assert reporter.close() == FlushResult(0, 0, 1, "unreachable")
    assert len(stub.calls) == 1
    assert sleeps == []
    with reporter:
        pass
    assert len(stub.calls) == 2  # leaving a with block is one attempt as well
    assert sleeps == []
    assert reporter.flush().error == "unreachable"
    assert len(stub.calls) == 6  # flush() still retries: 1 try and 3 retries


def test_the_backoff_is_capped_at_60_seconds(tmp_path):
    reporter, stub, sleeps = make(
        tmp_path, 503, max_retries=8, backoff_s=10.0, total_timeout_s=10_000
    )
    reporter.metric("m", 1)
    assert reporter.flush().error == "unreachable"
    assert len(stub.calls) == 9
    assert sleeps == [10.0, 20.0, 40.0, 60.0, 60.0, 60.0, 60.0, 60.0]


def test_a_huge_retry_count_does_not_overflow_the_backoff(tmp_path):
    reporter, stub, sleeps = make(tmp_path, 503, max_retries=1100, backoff_s=0.0)
    reporter.metric("m", 1)
    assert reporter.flush().error == "unreachable"
    assert len(stub.calls) == 1101
    assert set(sleeps) == {0.0}


@pytest.mark.parametrize("seconds", [0, -1, float("nan")])
def test_total_timeout_must_be_above_zero(seconds):
    with pytest.raises(ValueError, match="total_timeout_s"):
        RuntimeReporter("s", total_timeout_s=seconds)


# -- corrupt lines are counted once, when they leave the buffer ---------------------------


def test_corrupt_lines_count_as_rejected_only_when_they_are_dropped(tmp_path):
    first, _, _ = make(tmp_path)
    first.metric("m", 1)
    with (tmp_path / "buf.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    reporter, stub, _ = make(tmp_path, 503, max_retries=0)
    # the receiver is down: both lines stay, and nothing is counted as rejected yet
    assert reporter.flush() == FlushResult(0, 0, 2, "unreachable")
    assert reporter.flush() == FlushResult(0, 0, 2, "unreachable")
    stub.statuses = [202]
    assert reporter.flush() == FlushResult(1, 1, 0, None)
    assert buffered(tmp_path) == []
