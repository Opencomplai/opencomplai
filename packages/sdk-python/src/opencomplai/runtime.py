"""
Runtime event reporter: buffer hashes and metadata locally, send them in batches.

``RuntimeReporter`` records four kinds of event (an agent decision, an action
outside its mandate, a metric, an incident) as one JSON line each in a local
buffer file, and ``flush()`` sends the buffer to ``POST {base_url}/v1/runtime-events``.
The body of that request is described by ``data/runtime_event.schema.json``.

Only hashes and metadata leave the machine. The tool input is hashed (the same
way ``AgentDecisionLog`` does it) and never stored or sent. A hash of a short or
guessable input can be reversed by trying candidates, so do not pass low-entropy
inputs you consider sensitive.

Recording never touches the network and never starts a thread. ``flush()`` is the
only call that does network I/O, and it reports failures as fixed codes in
``FlushResult.error``: it never raises for a network problem and never repeats an
exception message, a response body or the API key. It is bounded, softly:
``total_timeout_s`` caps the whole call across attempts and batches (each network step
waits at most the time left, but a name lookup or a peer that sends slowly can overrun
it), the pause between attempts never exceeds 60 seconds, and ``close()`` makes a single
attempt. A request body never exceeds 200000 bytes: a flush splits the buffer by size as
well as by ``batch_size``.

The buffer folder is created 0o700 and the buffer, rejected and temporary files 0o600,
and a symbolic link in place of one of them is refused where the platform allows it.

Honest ceilings: one process per buffer file (the lock is in-process only), and
one buffer file per ``system_id`` (the batch carries a single system id). A second
reporter for another system on the same file raises ``ValueError``, but only inside
one process: nothing checks across processes.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import math
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from opencomplai_core.custom_pack import HIDDEN_CHARACTERS
from opencomplai_core.signing import canonical_json_bytes
from opencomplai_core.summaries import IncidentClass

__all__ = ["FlushResult", "RuntimeReporter"]

_log = logging.getLogger("opencomplai.runtime")

_OUTCOMES = ("success", "failure", "blocked")
_SEVERITIES = ("low", "medium", "high", "critical")
_MAX_BATCH = 100
_MAX_SYSTEM_ID = 200
_MAX_LABEL = 128
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
# What a label may not hold: C0 and C1 controls and the characters that hide or reorder
# text, the same class as the text of a custom pack (a receiver stores and shows these
# values). Unpaired surrogates are caught by `_encodable`.
_UNSAFE_TEXT = re.compile(rf"[\x00-\x1f\x7f-\x9f{HIDDEN_CHARACTERS}]")
_API_KEY = re.compile(r"[\x21-\x7e]+")
_URL_CHARS = re.compile(r"[\x21-\x7e]+")
_METRIC_NAME = re.compile(r"[a-z][a-z0-9_.]{0,63}")
_METRIC_UNIT = re.compile(r"[a-z%/_]{1,16}")
_SDK_VERSION = re.compile(r"[0-9A-Za-z.+-]{1,32}")
_MAX_METRIC = 1e15  # the schema's bound on a metric value, in both directions
_KEEP_4XX = frozenset({404, 405, 408, 410, 429})  # 4xx answers that are retried
_MAX_BODY_BYTES = 200_000  # a POST body stays well under the receiver's 262144 cap
_MAX_BACKOFF_S = 60.0
_monotonic = time.monotonic  # tests replace it to move the flush deadline

# Buffer file -> the system id that owns it, for this process.
_BUFFER_OWNERS: dict[str, str] = {}
_OWNERS_LOCK = threading.Lock()

#: A transport takes ``(url, headers, body, timeout_s)`` and returns the HTTP status.
#: It raises for a network failure. It must not follow redirects.
Transport = Callable[[str, Mapping[str, str], bytes, float], int]


@dataclass(frozen=True)
class FlushResult:
    """Outcome of one ``flush()``.

    ``sent`` counts events the server took (new or already seen), ``rejected``
    events it refused as invalid (moved to ``<buffer_path>.rejected.jsonl``) plus the
    corrupt buffer lines dropped, and ``remaining`` events still in the buffer.
    ``error`` is ``None`` or one of
    ``not_configured``, ``unreachable``, ``unauthorized`` or ``buffer_error``.
    """

    sent: int
    rejected: int
    remaining: int
    error: str | None


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    # A redirect would replay the Authorization header at another host.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# Private openers: never install_opener, so no other urllib caller is affected.
_OPENER = urllib.request.build_opener(_NoRedirectHandler)
# An http URL is always to this machine (see `_checked_url`): no environment proxy
# may see the Bearer key. https keeps the environment's proxy settings.
_LOCAL_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), _NoRedirectHandler
)


def _urllib_transport(
    url: str, headers: Mapping[str, str], body: bytes, timeout_s: float
) -> int:
    request = urllib.request.Request(
        url, data=body, headers=dict(headers), method="POST"
    )
    opener = _LOCAL_OPENER if urlparse(url).scheme == "http" else _OPENER
    try:
        with opener.open(request, timeout=timeout_s) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        exc.close()
        return int(exc.code)


def _label(value: object, what: str, *, maximum: int = _MAX_LABEL) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or not value.strip()  # the schema refuses `^\s*$` too
        or _UNSAFE_TEXT.search(value)
        or not _encodable(value)
    ):
        raise ValueError(
            f"{what} must be a string of 1 to {maximum} characters that is not only "
            "white space, without control characters, hidden or reordering "
            "characters or unpaired surrogates"
        )
    return value


def _encodable(text: str) -> bool:
    """False for a string with an unpaired surrogate, which has no UTF-8 form."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _choice(value: object, allowed: tuple[str, ...], what: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{what} must be one of {', '.join(allowed)}")
    return value


def _checked_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    try:
        parsed = urlparse(url)
        parsed.port  # noqa: B018 - raises ValueError for a malformed port
    except ValueError:
        parsed = None
    if (
        parsed is None
        or not _URL_CHARS.fullmatch(url)
        or not (
            parsed.scheme == "https"
            or (parsed.scheme == "http" and parsed.hostname in _LOCAL_HOSTS)
        )
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "base_url must be an https URL without credentials, query or fragment "
            "(http only to localhost, 127.0.0.1 or ::1)"
        )
    return url


def _classify(status: int | None) -> str:
    if status is not None and 200 <= status < 300:
        return "ok"
    if status in (401, 403):
        return "unauthorized"
    # 404, 405 and 410 mean a wrong or retired address, not a bad batch: keep the events.
    if status is not None and 400 <= status < 500 and status not in _KEEP_4XX:
        return "rejected"
    return (
        "retry"  # 408, 429, 404, 405, 410, 5xx, a network error, or anything unexpected
    )


def _private_opener(path: str, flags: int) -> int:
    """Open a buffer file private to the user (0o600 when created) and never through a
    symbolic link where the platform can refuse one."""
    return os.open(path, flags | getattr(os, "O_NOFOLLOW", 0), 0o600)


def _read_lines(path: Path) -> list[str]:
    try:
        with open(
            path, encoding="utf-8", errors="replace", opener=_private_opener
        ) as handle:
            return handle.read().splitlines()
    except FileNotFoundError:
        return []


def _write_atomic(path: Path, lines: list[str]) -> None:
    # mkstemp creates the file 0o600 under a fresh name: nothing predictable to
    # pre-create as a link, and os.replace swaps in a link's place, never its target.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("".join(f"{line}\n" for line in lines))
        os.replace(tmp, path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)  # only left behind when the write or the replace failed


def _claim_buffer(path: Path, system_id: str) -> None:
    try:
        resolved = str(path.resolve())  # `a/../x` and a link claim one file
    except (OSError, RuntimeError):  # a link loop, or a path the system cannot read
        resolved = os.path.abspath(path)  # its own spelling, with `..` folded
    key = os.path.normcase(resolved)
    with _OWNERS_LOCK:
        if _BUFFER_OWNERS.setdefault(key, system_id) != system_id:
            raise ValueError(
                "buffer_path is already used by a reporter for another system_id; "
                "use one buffer file per system"
            )


def _sdk_version() -> str | None:
    from opencomplai import __version__  # late: the package imports this module

    return __version__ if _SDK_VERSION.fullmatch(__version__) else None


class RuntimeReporter:
    def __init__(
        self,
        system_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        buffer_path: str | Path = ".opencomplai/runtime-events.jsonl",
        batch_size: int = _MAX_BATCH,
        max_buffered: int = 10_000,
        max_retries: int = 3,
        backoff_s: float = 0.5,
        timeout_s: float = 10.0,
        total_timeout_s: float = 30.0,
        transport: Transport | None = None,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Any] = time.sleep,
    ) -> None:
        self._system_id = _label(system_id, "system_id", maximum=_MAX_SYSTEM_ID)
        if not 1 <= batch_size <= _MAX_BATCH:
            raise ValueError(f"batch_size must be between 1 and {_MAX_BATCH}")
        if (
            max_buffered < 1
            or max_retries < 0
            or backoff_s < 0
            or timeout_s <= 0
            or not total_timeout_s > 0
        ):
            raise ValueError(
                "max_buffered must be at least 1, max_retries and backoff_s at least 0, "
                "and timeout_s and total_timeout_s above 0"
            )
        key = api_key or os.environ.get("OPENCOMPLAI_API_KEY") or None
        url = base_url or os.environ.get("OPENCOMPLAI_DASHBOARD_URL") or None
        if key is not None and not _API_KEY.fullmatch(key):
            raise ValueError("api_key must contain only printable ASCII characters")
        self._api_key = key
        self._endpoint = f"{_checked_url(url)}/v1/runtime-events" if url else None
        self._path = Path(buffer_path).absolute()
        _claim_buffer(self._path, self._system_id)
        self._rejected_path = self._path.with_name(self._path.name + ".rejected.jsonl")
        self._batch_size = batch_size
        self._max_buffered = max_buffered
        self._max_retries = max_retries
        self._backoff_s = backoff_s
        self._timeout_s = timeout_s
        self._total_timeout_s = total_timeout_s
        self._transport = transport or _urllib_transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleep = sleep
        self._lock = threading.Lock()  # guards the buffer file and the counters
        self._flush_lock = threading.Lock()  # one flush at a time
        self._dropped = 0
        self._warned = False
        try:
            self._count = sum(1 for line in _read_lines(self._path) if line.strip())
        except OSError:
            self._count = 0  # unreadable now: recording drops, flush reports it

    # -- recording: no network, no thread ---------------------------------

    def decision(
        self,
        agent_id: str,
        tool: str,
        outcome: str,
        tool_input: object,
        mandate_ref: str | None = None,
    ) -> None:
        self._record(
            "decision_log",
            agent_id=_label(agent_id, "agent_id"),
            tool=_label(tool, "tool"),
            outcome=_choice(outcome, _OUTCOMES, "outcome"),
            input_hash=_input_hash(tool_input),
            **_mandate(mandate_ref),
        )

    def out_of_mandate(
        self,
        agent_id: str,
        tool: str,
        tool_input: object,
        mandate_ref: str | None = None,
    ) -> None:
        self._record(
            "out_of_mandate",
            agent_id=_label(agent_id, "agent_id"),
            tool=_label(tool, "tool"),
            input_hash=_input_hash(tool_input),
            **_mandate(mandate_ref),
        )

    def metric(self, name: str, value: float, unit: str | None = None) -> None:
        if not isinstance(name, str) or not _METRIC_NAME.fullmatch(name):
            raise ValueError("name must match [a-z][a-z0-9_.]{0,63}")
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("value must be a finite number")
        try:
            in_range = math.isfinite(value) and abs(value) <= _MAX_METRIC
        except OverflowError:
            in_range = False
        if not in_range:
            raise ValueError("value must be a finite number between -1e15 and 1e15")
        extra: dict[str, Any] = {}
        if unit is not None:
            if not isinstance(unit, str) or not _METRIC_UNIT.fullmatch(unit):
                raise ValueError("unit must match [a-z%/_]{1,16}")
            extra["unit"] = unit
        self._record("metric", name=name, value=value, **extra)

    def incident(self, severity: str, incident_class: str | IncidentClass) -> None:
        self._record(
            "incident",
            severity=_choice(severity, _SEVERITIES, "severity"),
            incident_class=IncidentClass(incident_class).value,
        )

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "buffered": self._count,
                "dropped": self._dropped,
                "configured": self._endpoint is not None and self._api_key is not None,
            }

    def _record(self, kind: str, **fields: Any) -> None:
        moment = self._clock()
        if moment.tzinfo is not None:
            moment = moment.astimezone(UTC)
        event = {
            "event_id": uuid.uuid4().hex,
            "kind": kind,
            "occurred_at": moment.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            **fields,
        }
        line = json.dumps(event, separators=(",", ":"), allow_nan=False)
        message: str | None = None
        with self._lock:
            if self._count >= self._max_buffered:
                message = "the runtime event buffer is full; new events are dropped"
            else:
                try:
                    self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with open(
                        self._path,
                        "a",
                        encoding="utf-8",
                        newline="\n",
                        opener=_private_opener,
                    ) as handle:
                        handle.write(line + "\n")
                    self._count += 1
                except OSError:
                    message = "the runtime event buffer could not be written"
            if message:
                self._dropped += 1
                if self._warned:
                    message = None  # one warning until a flush makes room again
                self._warned = True
        if message:
            # outside the lock: a logging handler may call back into the reporter
            _log.warning(message)

    # -- sending ----------------------------------------------------------

    def flush(self) -> FlushResult:
        return self._flush(self._max_retries)

    def _flush(self, retries: int) -> FlushResult:
        with self._flush_lock:
            if self._endpoint is None or self._api_key is None:
                return FlushResult(0, 0, self.stats()["buffered"], "not_configured")
            try:
                with self._lock:
                    lines = _read_lines(self._path)
                deadline = _monotonic() + self._total_timeout_s
                return self._send(lines, retries, deadline)
            except OSError:
                return FlushResult(0, 0, self.stats()["buffered"], "buffer_error")

    def _send(self, lines: list[str], retries: int, deadline: float) -> FlushResult:
        sent = rejected = 0
        error: str | None = None
        for run, good, events, corrupt in self._runs(lines):
            if events:
                outcome = self._post(events, retries, deadline)
                if outcome in ("unauthorized", "unreachable"):
                    error = outcome
                    break
                if outcome == "rejected":
                    rejected += len(good)
                    self._keep_rejected(good)
                else:
                    sent += len(good)
            # A corrupt line is dropped, never sent, and counted once: only here,
            # where it leaves the buffer, and not on a run that stays for the next flush.
            rejected += corrupt
            self._drop(run)
        with self._lock:
            if self._count < self._max_buffered:
                self._warned = False
            remaining = self._count
        return FlushResult(sent, rejected, remaining, error)

    def _runs(
        self, lines: list[str]
    ) -> Iterator[tuple[list[str], list[str], list[dict[str, Any]], int]]:
        """Split the buffer into runs of consecutive lines, each with at most `batch_size`
        events and a POST body of at most `_MAX_BODY_BYTES`. Yields `(run, good lines,
        events, corrupt line count)`; blank and corrupt lines travel with the run
        they sit in, so every line is dropped with exactly one run."""
        base = len(self._body([]))
        run: list[str] = []
        good: list[str] = []
        events: list[dict[str, Any]] = []
        corrupt = size = 0
        for line in lines:
            if line.strip():
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError
                    # the size of the event as it is posted, UTF-8 and without escapes
                    width = len(_dumps(event).encode("utf-8")) + 1
                except (ValueError, RecursionError):
                    event, width = None, 0
                if event is not None:
                    if events and (
                        len(events) >= self._batch_size
                        or base + size + width > _MAX_BODY_BYTES
                    ):
                        yield run, good, events, corrupt
                        run, good, events, corrupt, size = [], [], [], 0, 0
                    good.append(line)
                    events.append(event)
                    size += width
                else:
                    corrupt += 1
            run.append(line)
        if run:
            yield run, good, events, corrupt

    def _body(self, events: list[dict[str, Any]]) -> bytes:
        batch: dict[str, Any] = {"schema_version": "1", "system_id": self._system_id}
        version = _sdk_version()
        if version:
            batch["sdk_version"] = version
        batch["events"] = events
        return _dumps(batch).encode("utf-8")

    def _post(self, events: list[dict[str, Any]], retries: int, deadline: float) -> str:
        body = self._body(events)
        version = _sdk_version()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"opencomplai-sdk/{version or 'unknown'}",
        }
        assert self._endpoint is not None
        for attempt in range(retries + 1):
            # ponytail: a soft bound. Each step waits at most the time left, but a DNS
            # lookup or a peer that trickles bytes can run past it; a hard bound needs
            # a worker thread or an async client.
            left = deadline - _monotonic()
            if left <= 0:
                return "unreachable"  # out of time: the events stay for the next flush
            try:
                status: int | None = self._transport(
                    self._endpoint, headers, body, min(self._timeout_s, left)
                )
            except Exception:
                status = None  # any failure counts as a network failure, never echoed
            outcome = _classify(status)
            if outcome != "retry":
                return outcome
            if attempt < retries:
                pause = min(_MAX_BACKOFF_S, self._backoff_s * 2 ** min(attempt, 30))
                self._sleep(max(0.0, min(pause, deadline - _monotonic())))
        return "unreachable"

    def _drop(self, done: list[str]) -> None:
        """Remove the lines just handled, matched by content and not by position, so
        a line another writer added or already removed is never taken for one of them."""
        gone = set(done)
        with self._lock:
            rest = [
                line
                for line in _read_lines(self._path)
                if line.strip() and line not in gone
            ]
            _write_atomic(self._path, rest)
            self._count = len(rest)

    def _keep_rejected(self, lines: list[str]) -> None:
        try:
            kept = (_read_lines(self._rejected_path) + lines)[-self._max_buffered :]
            _write_atomic(self._rejected_path, kept)
        except OSError:
            _log.warning("the rejected runtime events could not be saved")

    def close(self) -> FlushResult:
        # One attempt and no backoff: a process that is closing must not wait on a
        # receiver that is down. What stays in the buffer is sent by a later run.
        return self._flush(0)

    def __enter__(self) -> RuntimeReporter:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _input_hash(tool_input: object) -> str:
    try:
        canonical = canonical_json_bytes({"input": tool_input})
    except (TypeError, ValueError, RecursionError):
        # mixed-type keys, a cycle or very deep nesting: no part of the input is echoed
        raise ValueError("tool_input cannot be serialised") from None
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _dumps(value: object) -> str:
    """Compact JSON as it is posted: UTF-8 characters stay as they are, so a label of
    astral characters is 4 bytes each and not a 12-byte escape pair."""
    return json.dumps(value, separators=(",", ":"), allow_nan=False, ensure_ascii=False)


def _mandate(mandate_ref: str | None) -> dict[str, Any]:
    return (
        {}
        if mandate_ref is None
        else {"mandate_ref": _label(mandate_ref, "mandate_ref")}
    )
