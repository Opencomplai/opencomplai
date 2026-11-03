"""The four ISO/IEC 27090 supporting probes: what each finds, and what it must not.

A probe is evidence for a row only through `supporting_gap_status`: a matched file
whose content markers hold. The probe's own row is Partial at most, never Met;
`build_gap_report` keeps an unattested row Unverified (test_supporting_sources.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.gap_probes import (
    _PROBE_PATTERNS,
    PROBE_PROVENANCE,
    STUB_SOURCE_REFS,
    artifact_gap_status,
    run_artifact_probe,
    supporting_gap_status,
)
from opencomplai_core.models import GapStatus

SHA = "9fceb02d0ae598e95dc970b74767f19372d61af8"  # a 40-hex commit hash
MD5 = "d41d8cd98f00b204e9800998ecf8427e"
SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
REFS = (
    "ai_supply_chain_pins",
    "rate_limiting_config",
    "ai_threat_model",
    "ai_red_team_report",
)


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _found(root: Path, ref: str) -> list[str] | None:
    """The paths a supporting probe reports, or None when it is silent."""
    row = supporting_gap_status(ref, root)
    if row is None:
        return None
    assert row.status == GapStatus.PARTIAL  # evidence, never Met
    return run_artifact_probe(ref, root).found_paths


@pytest.mark.parametrize("ref", REFS)
def test_probe_is_registered_with_provenance(ref: str):
    assert ref in _PROBE_PATTERNS
    assert ref not in STUB_SOURCE_REFS["artifact"]
    entry = PROBE_PROVENANCE[ref]
    assert entry["confidence"] == "low"
    assert entry["needs_founder_review"] is True
    assert "27090" in entry["source"]


@pytest.mark.parametrize("ref", REFS)
def test_an_empty_repo_and_no_repo_are_silent(tmp_path: Path, ref: str):
    assert supporting_gap_status(ref, tmp_path) is None
    assert supporting_gap_status(ref, None) is None


# --- ai_supply_chain_pins ---------------------------------------------------------


@pytest.mark.parametrize(
    ("rel", "text"),
    [
        ("sbom.json", '{"bomFormat": "CycloneDX", "specVersion": "1.5"}'),
        ("out/app.cdx.json", '{"bomFormat": "CycloneDX"}'),
        ("bom.json", '{"spdxVersion": "SPDX-2.3"}'),
        ("release/app.spdx.json", '{"spdxVersion": "SPDX-2.3"}'),
        ("dvc.lock", f"stages:\n  train:\n    outs:\n    - md5: {MD5}\n"),
        ("data/train.csv.dvc", f"outs:\n- md5: {MD5}\n  path: train.csv\n"),
        ("models.lock.json", f'{{"bert": {{"sha256": "{SHA256}"}}}}'),
        ("ml/model-pins.yaml", f"embedder:\n  sha256: {SHA256}\n"),
        (
            "app/load.py",
            "model = AutoModel.from_pretrained(\n"
            f'    "org/model",\n    revision="{SHA}",\n    trust_remote_code=False,\n)\n',
        ),
        ("app/dl.py", f'hf_hub_download("org/m", "w.bin", revision="{SHA[:12]}")\n'),
    ],
)
def test_supply_chain_pins_are_found(tmp_path: Path, rel: str, text: str):
    assert _found(_write(tmp_path, {rel: text}), "ai_supply_chain_pins") == [rel]


@pytest.mark.parametrize(
    ("rel", "text"),
    [
        ("sbom.json", "{}"),  # named like an SBOM, not one
        ("bom.json", '{"parts": ["bolt", "nut"]}'),
        ("dvc.lock", "schema: '2.0'\nstages: {}\n"),  # no hash
        ("models.lock.json", '{"bert": {"version": "1.2"}}'),
        ("app/load.py", 'AutoModel.from_pretrained("org/model")\n'),  # unpinned
        ("app/load.py", 'AutoModel.from_pretrained("org/model", revision="main")\n'),
        ("app/load.py", 'AutoModel.from_pretrained("org/m", revision="v1.2")\n'),
        ("app/util.py", f"digest = hashlib.sha256(blob).hexdigest()  # {SHA256}\n"),
        ("uv.lock", f'sha256 = "{SHA256}"\n'),  # dependency lock files are not read
        ("docs/sbom.md", '"bomFormat": "CycloneDX"'),
        (  # the installed packages of a Python environment
            "venv/lib/python3.11/site-packages/hub/x.py",
            f'm.from_pretrained("a/b", revision="{SHA}")\n',
        ),
    ],
)
def test_supply_chain_look_alikes_are_not_evidence(tmp_path: Path, rel: str, text: str):
    assert _found(_write(tmp_path, {rel: text}), "ai_supply_chain_pins") is None


def test_a_pin_is_found_behind_five_files_that_match_the_glob_but_not_the_markers(
    tmp_path: Path,
):
    files = {f"src/a{n}.py": "print('no pins here')\n" for n in range(7)}
    files["src/z.py"] = f'm.from_pretrained("a/b", revision="{SHA}")\n'
    assert _found(_write(tmp_path, files), "ai_supply_chain_pins") == ["src/z.py"]


# --- rate_limiting_config ---------------------------------------------------------


@pytest.mark.parametrize(
    ("rel", "text"),
    [
        ("app/main.py", "from slowapi import Limiter\n"),
        ("app/main.py", "import flask_limiter\n"),
        ("app/main.py", "from fastapi_limiter import FastAPILimiter\n"),
        ("app/views.py", "from django_ratelimit.decorators import ratelimit\n"),
        ("config/settings.py", "REST_FRAMEWORK = {'DEFAULT_THROTTLE_RATES': {}}\n"),
        ("server.js", "const rateLimit = require('express-rate-limit');\n"),
        ("src/app.ts", 'import rateLimit from "express-rate-limit";\n'),
        ("src/app.mjs", "await app.register(import('@fastify/rate-limit'));\n"),
        (
            "src/app.js",
            "const { RateLimiterMemory } = require('rate-limiter-flexible')\n",
        ),
        (
            "deploy/nginx.conf",
            "http {\n  limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;\n}\n",
        ),
        ("deploy/site.conf", "location /v1 {\n    limit_req zone=api burst=20;\n}\n"),
        (
            "deploy/envoy.yaml",
            "http_filters:\n- name: envoy.filters.http.local_ratelimit\n",
        ),
    ],
)
def test_rate_limits_are_found(tmp_path: Path, rel: str, text: str):
    assert _found(_write(tmp_path, {rel: text}), "rate_limiting_config") == [rel]


@pytest.mark.parametrize(
    ("rel", "text"),
    [
        ("README.md", "We use slowapi and express-rate-limit.\n"),
        ("package.json", '{"dependencies": {"express-rate-limit": "^7.0.0"}}'),
        ("pnpm-lock.yaml", "  '@fastify/rate-limit':\n    specifier: ^11.2.1\n"),
        ("src/notes.ts", "// register express-rate-limit before the routes\n"),
        ("requirements.txt", "slowapi==0.1.9\n"),
        ("app/main.py", "limit_req = 5\n"),  # a variable, not the nginx directive
        ("app/main.py", "# TODO: rate limiting\nlimit = 5\n"),
        ("deploy/nginx.conf", "limit_req_status 429;\n"),
        ("deploy/nginx.conf", "# limit_req_zone $binary_remote_addr zone=a:1m;\n"),
        ("deploy/envoy.yaml", "- name: envoy.filters.http.router\n"),
        (
            "venv/Lib/site-packages/slowapi/x.py",  # an installed copy
            "from slowapi import Limiter\n",
        ),
    ],
)
def test_rate_limit_look_alikes_are_not_evidence(tmp_path: Path, rel: str, text: str):
    assert _found(_write(tmp_path, {rel: text}), "rate_limiting_config") is None


# --- ai_threat_model --------------------------------------------------------------

THREAT_MODEL = (
    "# Threat model\n\nAn attacker can use prompt injection in retrieved documents "
    "to make the assistant call tools it should not call.\n"
)


@pytest.mark.parametrize(
    "rel",
    [
        "docs/threat-model.md",
        "THREAT_MODEL.md",
        "security/threat_model.rst",
        "docs/security/threat-model-v2.md",
        "docs/threat-modelling.md",
        "docs/threat-model/overview.md",
    ],
)
def test_threat_models_are_found(tmp_path: Path, rel: str):
    assert _found(_write(tmp_path, {rel: THREAT_MODEL}), "ai_threat_model") == [rel]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "# Threat model\n\n## Prompt injection\n",  # headings only
        "# Threat model\n\nTo be written before the first release.\n",
        # a model of an ordinary web service
        "Attackers may try SQL injection or cross-site scripting against the "
        "login form and the admin console of the service.\n",
        # ambiguous words alone are not AI attacks
        "The perimeter IDS can miss evasion techniques, and an attacker could leave "
        "a backdoor in the admin console of the service.\n",
    ],
)
def test_threat_model_look_alikes_are_not_evidence(tmp_path: Path, text: str):
    repo = _write(tmp_path, {"docs/threat-model.md": text})
    assert _found(repo, "ai_threat_model") is None
    # The file exists, so a primary use still sees a candidate, never a pass.
    assert artifact_gap_status("ai_threat_model", repo).status == GapStatus.PARTIAL


def test_threat_model_terms(tmp_path: Path):
    for term in (
        "data poisoning",
        "Model-poisoning",
        "evasion attack",
        "membership inference",
        "model inversion",
        "model extraction",
        "model exfiltration",
        "model backdoor",
        "jailbreak",
    ):
        text = f"# Threat model\n\nThe main risk we track for this system is {term} by users.\n"
        repo = _write(tmp_path / term.replace(" ", "_"), {"THREAT_MODEL.md": text})
        assert _found(repo, "ai_threat_model") == ["THREAT_MODEL.md"], term


# --- ai_red_team_report -----------------------------------------------------------

RED_TEAM = (
    "# Red team round 1\n\nWe tried jailbreak and prompt injection prompts against "
    "the assistant. Results: 3 of 40 attempts bypassed the output filter.\n"
)


@pytest.mark.parametrize(
    "rel",
    [
        "docs/red-team-2026-10.md",
        "RED_TEAM_REPORT.md",
        "reports/red-team/round1.md",
        "docs/security/adversarial-testing.md",
    ],
)
def test_red_team_reports_are_found(tmp_path: Path, rel: str):
    assert _found(_write(tmp_path, {rel: RED_TEAM}), "ai_red_team_report") == [rel]


@pytest.mark.parametrize(
    "text",
    [
        "",
        # a plan: no result yet
        "We plan to try jailbreak and prompt injection prompts against the assistant "
        "during the second quarter, with two people.\n",
        # a report, but not about AI attacks
        "Penetration test results: two findings in the login page, both fixed before "
        "the release of version two.\n",
    ],
)
def test_red_team_look_alikes_are_not_evidence(tmp_path: Path, text: str):
    assert (
        _found(_write(tmp_path, {"docs/red-team.md": text}), "ai_red_team_report")
        is None
    )


def test_the_event_log_probe_is_the_one_row_7_5_uses(tmp_path: Path):
    repo = _write(tmp_path, {".opencomplai/oversight-log.json": '{"seq": 1}\n'})
    assert _found(repo, "event_log_evidence") == [".opencomplai/oversight-log.json"]
