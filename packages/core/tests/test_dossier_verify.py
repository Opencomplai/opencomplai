"""Dossier verification: only Ed25519 verifies; every other state is rejected distinctly."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest
from opencomplai_core.dossier_generator import BUNDLE_EXCLUDE, generate_dossier
from opencomplai_core.dossier_verify import verify_dossier
from opencomplai_core.engine import assess
from opencomplai_core.models import AssessmentInput, ModelMetadata, SystemManifest
from opencomplai_core.signing import generate_keypair


@pytest.fixture(autouse=True)
def _clean_signing_env(monkeypatch):
    for name in (
        "DOSSIER_SIGNING_KEY_PATH",
        "LOCAL_SIGNING_KEY_PATH",
        "SIGNING_KEY_PRIVATE",
    ):
        monkeypatch.delenv(name, raising=False)


def _generate(monkeypatch, key: str | None = None) -> dict:
    if key is None:
        monkeypatch.delenv("DOSSIER_SIGNING_KEY_PATH", raising=False)
    else:
        monkeypatch.setenv("DOSSIER_SIGNING_KEY_PATH", key)
    manifest = SystemManifest(
        system_id="t",
        intended_purpose="chatbot",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=False,
        commit_ref="abc123",
    )
    risk = assess(
        AssessmentInput(
            model=ModelMetadata(
                name="t",
                version="1.0.0",
                modality="text",
                use_case="chatbot",
                deployment_context="production",
            )
        )
    )
    return json.loads(generate_dossier(manifest, risk).model_dump_json())


def _signed(tmp_path, monkeypatch, name="keys"):
    key_dir = tmp_path / name
    generate_keypair(key_dir)
    return _generate(monkeypatch, str(key_dir / "signing.key")), key_dir / "signing.pub"


def test_valid_ed25519_dossier_verifies(tmp_path, monkeypatch):
    dossier, pub = _signed(tmp_path, monkeypatch)
    verdict = verify_dossier(dossier, pub)
    assert verdict.ok
    assert verdict.code == "OK"


def test_hmac_local_dossier_is_rejected(tmp_path, monkeypatch):
    _, pub = _signed(tmp_path, monkeypatch)
    dossier = _generate(monkeypatch)  # unsigned base, then forge a legacy HMAC one
    from opencomplai_core.dossier import AnnexIVDossier

    bundle = (
        AnnexIVDossier.model_validate(dossier)
        .model_dump_json(exclude=BUNDLE_EXCLUDE)
        .encode()
    )
    dossier["signature"] = base64.b64encode(
        hmac.new(b"k", bundle, hashlib.sha256).digest()
    ).decode()
    dossier["signature_status"] = "hmac-local"
    verdict = verify_dossier(dossier, pub)
    assert not verdict.ok
    assert verdict.code == "UNSUPPORTED_SIGNATURE"


def test_unsigned_dossier_is_rejected_distinctly(tmp_path, monkeypatch):
    dossier, pub = _signed(tmp_path, monkeypatch)
    unsigned = verify_dossier(_generate(monkeypatch), pub)
    dossier["section1"]["intended_purpose"] = "changed"
    tampered = verify_dossier(dossier, pub)
    assert not unsigned.ok
    assert unsigned.code == "UNSIGNED"
    assert unsigned.code not in {"UNSUPPORTED_SIGNATURE", tampered.code}


def test_tampered_dossier_is_rejected(tmp_path, monkeypatch):
    dossier, pub = _signed(tmp_path, monkeypatch)
    dossier["section1"]["intended_purpose"] = "something else entirely"
    verdict = verify_dossier(dossier, pub)
    assert not verdict.ok
    assert verdict.code == "CHECKSUM_MISMATCH"


def test_wrong_key_is_rejected(tmp_path, monkeypatch):
    dossier, _ = _signed(tmp_path, monkeypatch)
    other = tmp_path / "other"
    generate_keypair(other)
    verdict = verify_dossier(dossier, other / "signing.pub")
    assert not verdict.ok
    assert verdict.code == "BAD_SIGNATURE"


def test_ed25519_label_with_hmac_value_is_rejected(tmp_path, monkeypatch):
    dossier, pub = _signed(tmp_path, monkeypatch)
    dossier["signature"] = base64.b64encode(
        hmac.new(b"k", b"x", hashlib.sha256).digest()
    ).decode()
    verdict = verify_dossier(dossier, pub)
    assert not verdict.ok
    assert verdict.code == "BAD_SIGNATURE"


@pytest.mark.parametrize(
    "hostile",
    [{}, {"dossier_id": 1}, {"signature": "x", "signature_status": "ed25519"}, []],
)
def test_malformed_input_never_raises(hostile, tmp_path):
    verdict = verify_dossier(hostile, tmp_path / "missing.pub")
    assert not verdict.ok
    assert verdict.code == "MALFORMED"


def test_garbage_signature_and_missing_key_never_raise(tmp_path, monkeypatch):
    dossier, pub = _signed(tmp_path, monkeypatch)
    dossier["signature"] = "!!not base64!!"
    assert verify_dossier(dossier, pub).code == "BAD_SIGNATURE"
    assert verify_dossier(dossier, tmp_path / "missing.pub").code == "BAD_SIGNATURE"
