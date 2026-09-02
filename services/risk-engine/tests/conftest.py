"""
Shared test fixtures for risk-engine.

Every /v1/* route except /v1/checker/* now requires a signed internal
service token (SEC-SERVICE-AUTH). Tests set a fixed shared secret and expose
a ready-made Authorization header so each test file's own `client` fixture
can attach it.
"""

from __future__ import annotations

import urllib.error as urlerr

import pytest
from opencomplai_core.service_auth import mint_service_token

TEST_SERVICE_TOKEN_SECRET = "risk-engine-test-secret"


@pytest.fixture(autouse=True)
def _service_token_secret(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN_SECRET", TEST_SERVICE_TOKEN_SECRET)


@pytest.fixture
def service_auth_headers() -> dict[str, str]:
    token = mint_service_token("test-caller", TEST_SERVICE_TOKEN_SECRET)
    return {"Authorization": f"Bearer {token}"}


class _FakeVault:
    """
    In-process stand-in for evidence-vault's HITL persistence routes
    (PERSIST-RISK). review_queue.py and main.py both now call evidence-vault
    over HTTP instead of touching process-local dicts; unit tests don't run a
    real evidence-vault, so this fixture monkeypatches each module's
    `_vault_request` to serve the same contract from an in-memory dict —
    same behavior the code exercises in production, just without the network
    hop, mirroring how _record_hitl_event is already mocked for ledger writes.
    """

    def __init__(self):
        self.review_items: dict[str, dict] = {}
        self.review_contexts: dict[str, dict] = {}
        self.accepted_overrides: dict[str, dict] = {}
        self.completed_evals: dict[str, dict] = {}
        # CTRL-FRESH (CTRL-STORE): controls bucketed by system_id, keyed by
        # control_id (mirrors the real PUT /v1/controls presence-based
        # upsert), and fingerprints keyed by system_id.
        self.controls: dict[str, dict[str, dict]] = {}
        self.fingerprints: dict[str, str] = {}

    def clear(self):
        self.review_items.clear()
        self.review_contexts.clear()
        self.accepted_overrides.clear()
        self.completed_evals.clear()
        self.controls.clear()
        self.fingerprints.clear()

    def __call__(self, method: str, path: str, body: dict | None = None) -> dict | None:
        if path == "/v1/hitl/review-items" and method == "PUT":
            self.review_items[body["review_id"]] = body
            return {"item": body}
        if path.startswith("/v1/hitl/review-items/") and method == "GET":
            review_id = path.rsplit("/", 1)[-1]
            item = self.review_items.get(review_id)
            if item is None:
                raise _NotFoundError()
            return {"item": item}
        if path.startswith("/v1/hitl/review-items") and method == "GET":
            query = path.split("?", 1)[1] if "?" in path else ""
            params = dict(p.split("=", 1) for p in query.split("&") if p)
            items = list(self.review_items.values())
            if "state" in params:
                items = [i for i in items if i["state"] == params["state"]]
            if "assigned_to" in params:
                items = [i for i in items if i["assigned_to"] == params["assigned_to"]]
            return {"items": items}
        if path == "/v1/hitl/review-contexts" and method == "POST":
            self.review_contexts.setdefault(body["context_ref"], body["context_json"])
            return {"context_ref": body["context_ref"]}
        if path.startswith("/v1/hitl/review-contexts/") and method == "GET":
            context_ref = path.rsplit("/", 1)[-1]
            context_json = self.review_contexts.get(context_ref)
            if context_json is None:
                raise _NotFoundError()
            return {"context_json": context_json}
        if path.startswith("/v1/hitl/overrides/") and method == "GET":
            idem_key = path.rsplit("/", 1)[-1]
            cached = self.accepted_overrides.get(idem_key)
            if cached is None:
                return {
                    "found": False,
                    "payload_fingerprint": None,
                    "response_json": None,
                }
            return {"found": True, **cached}
        if path == "/v1/hitl/overrides" and method == "POST":
            self.accepted_overrides.setdefault(
                body["idempotency_key"],
                {
                    "payload_fingerprint": body["payload_fingerprint"],
                    "response_json": body["response_json"],
                },
            )
            return {"idempotency_key": body["idempotency_key"]}
        if path.startswith("/v1/evals/cache/") and method == "GET":
            run_id = path.rsplit("/", 1)[-1]
            cached = self.completed_evals.get(run_id)
            if cached is None:
                return {"found": False, "result_json": None}
            return {"found": True, "result_json": cached}
        if path == "/v1/evals/cache" and method == "POST":
            self.completed_evals.setdefault(body["eval_run_id"], body["result_json"])
            return {"eval_run_id": body["eval_run_id"]}
        if method == "GET" and path.startswith("/v1/controls/"):
            system_id = path.rsplit("/", 1)[-1]
            return {"items": list(self.controls.get(system_id, {}).values())}
        if method == "PUT" and path == "/v1/controls":
            assert body is not None
            items = []
            for item in body["items"]:
                # Presence-based patch: merge onto any existing row, keyed by
                # control_id, mirroring evidence-vault's upsert_controls.
                system_bucket = None
                for bucket in self.controls.values():
                    if item["control_id"] in bucket:
                        system_bucket = bucket
                        break
                if system_bucket is not None:
                    system_bucket[item["control_id"]].update(item)
                    items.append(system_bucket[item["control_id"]])
                else:
                    bucket = self.controls.setdefault(item["system_id"], {})
                    bucket[item["control_id"]] = item
                    items.append(item)
            return {"items": items}
        if method == "GET" and path.startswith("/v1/fingerprints/"):
            system_id = path.rsplit("/", 1)[-1]
            fingerprint = self.fingerprints.get(system_id)
            if fingerprint is None:
                raise urlerr.HTTPError(path, 404, "Fingerprint not found", None, None)
            return {"fingerprint": fingerprint}
        if method == "PUT" and path.startswith("/v1/fingerprints/"):
            assert body is not None
            system_id = path.rsplit("/", 1)[-1]
            self.fingerprints[system_id] = body["fingerprint"]
            return {"fingerprint": body["fingerprint"]}
        raise AssertionError(f"unhandled fake-vault request: {method} {path}")


class _NotFoundError(Exception):
    pass


def _wrap_get_review_item_and_context(fake: _FakeVault, monkeypatch):
    """
    review_queue.get_review_item/get_review_context bypass _vault_request and
    call urlreq.urlopen directly (they need real urllib.error.HTTPError
    semantics for the 404-vs-raise distinction) — patch those two functions
    directly instead of urlopen itself, which is simpler than faking the
    HTTPResponse/HTTPError protocol.
    """

    def _get_review_item(tenant_id, review_id):
        from opencomplai_risk_engine.review_queue import _item_to_model

        item = fake.review_items.get(review_id)
        return _item_to_model(item) if item is not None else None

    def _get_review_context(context_ref_value):
        from opencomplai_core.models import RedactedReviewContext

        context_json = fake.review_contexts.get(context_ref_value)
        return (
            RedactedReviewContext.model_validate(context_json)
            if context_json is not None
            else None
        )

    monkeypatch.setattr(
        "opencomplai_risk_engine.review_queue.get_review_item", _get_review_item
    )
    monkeypatch.setattr(
        "opencomplai_risk_engine.review_queue.get_review_context", _get_review_context
    )


@pytest.fixture
def fake_vault(monkeypatch):
    """
    Autouse-able fixture that routes all evidence-vault HITL/override/eval-
    cache/control-registry calls made by main.py, review_queue.py, and
    control_reassessment.py to a shared in-memory store for the duration of
    a test. Yields the _FakeVault instance so tests can inspect or clear it
    directly.
    """
    fake = _FakeVault()
    monkeypatch.setattr("opencomplai_risk_engine.main._vault_request", fake)
    monkeypatch.setattr("opencomplai_risk_engine.review_queue._vault_request", fake)
    monkeypatch.setattr(
        "opencomplai_risk_engine.control_reassessment._vault_request", fake
    )
    _wrap_get_review_item_and_context(fake, monkeypatch)
    return fake
