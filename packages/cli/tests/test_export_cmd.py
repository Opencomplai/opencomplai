"""`opencomplai export`: one neutral evidence package from a signed artifact."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import jsonschema
import opencomplai_core
import pytest
from opencomplai_cli.main import app
from opencomplai_core import signing
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
    ScanResult,
    ScanStatusArtifact,
)
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
_MARKER = "SECRET-RATIONALE-TEXT"
_SCHEMA = (
    Path(opencomplai_core.__file__).parent / "data" / "evidence_package.schema.json"
)
_ROWS = [
    ("Art. 9", GapStatus.MISSING, ArticleGapSource.RULE, "R-9", _MARKER, 0.4),
    ("Art. 10", GapStatus.MET, ArticleGapSource.EVALUATOR, "none", "", None),
    ("Art. 15", GapStatus.PARTIAL, ArticleGapSource.OBLIGATION, "OBL-15", "", 0.8),
]


def _artifact(system_id: str = "sys-1") -> ScanStatusArtifact:
    return ScanStatusArtifact(
        install_id="i",
        system_id=system_id,
        commit_ref="abc1234",
        result=ScanResult.CONTROL_FAIL,
        failed_controls=["C-1"],
        evidence_hashes=["a" * 64],
        rationale_hash="0" * 64,
        duration_ms=5,
        rule_set_version="2026.10",
        cli_version="0.9.1",
        gap_report=GapReport(
            system_id=system_id,
            commit_ref="abc1234",
            generated_at="2026-10-06T00:00:00+00:00",
            articles=[
                ArticleGapStatus(
                    article=a,
                    status=s,
                    source=src,
                    evidence_ref=ref,
                    rationale=why,
                    confidence=conf,
                )
                for a, s, src, ref, why, conf in _ROWS
            ],
        ),
    )


def _signed(tmp_path: Path, system_id: str = "sys-1") -> tuple[Path, Path]:
    keys = tmp_path / "keys"
    generate_keypair(keys)
    art = _artifact(system_id)
    art.signature = signing.sign_artifact(art, keys / "signing.key")
    src = tmp_path / "compliance-artifact.json"
    src.write_text(art.model_dump_json(indent=2), encoding="utf-8")
    return src, keys / "signing.pub"


def _export(src: Path, *args: str):
    return runner.invoke(app, ["export", str(src), *args])


def test_package_validates_against_published_schema(tmp_path):
    src, _ = _signed(tmp_path)
    res = _export(src)
    assert res.exit_code == 0, res.output
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    pkg = json.loads(res.stdout)
    jsonschema.validate(pkg, schema)
    assert pkg["package_version"] == "1"
    assert pkg["verification"]["signed"] is True
    assert [a["article"] for a in pkg["articles"]] == ["Art. 9", "Art. 10", "Art. 15"]
    # The model-dependent extras are rejected: the schema is closed.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**pkg, "extra": 1}, schema)


def test_embedded_artifact_is_unchanged_and_verifies(tmp_path):
    src, pub = _signed(tmp_path)
    pkg = json.loads(_export(src).stdout)
    assert pkg["artifact"] == json.loads(src.read_text(encoding="utf-8"))
    embedded = ScanStatusArtifact.model_validate(pkg["artifact"])
    assert signing.verify_artifact(embedded, pub) is True


def test_artifact_out_verifies_with_verify_command(tmp_path):
    src, pub = _signed(tmp_path)
    out = tmp_path / "embedded.json"
    res = _export(src, "--artifact-out", str(out))
    assert res.exit_code == 0, res.output
    ok = runner.invoke(
        app, ["verify", str(out), "--kind", "artifact", "--pub-key", str(pub)]
    )
    assert ok.exit_code == 0, ok.output
    tampered = json.loads(out.read_text(encoding="utf-8"))
    tampered["system_id"] = "someone-else"
    bad = tmp_path / "tampered.json"
    bad.write_text(json.dumps(tampered), encoding="utf-8")
    res = runner.invoke(
        app, ["verify", str(bad), "--kind", "artifact", "--pub-key", str(pub)]
    )
    assert res.exit_code == 1


def test_csv_has_one_row_per_article(tmp_path):
    src, _ = _signed(tmp_path)
    res = _export(src, "--format", "csv")
    assert res.exit_code == 0, res.output
    rows = list(csv.reader(io.StringIO(res.stdout, newline="")))
    assert rows[0] == [
        "system_id",
        "commit_ref",
        "rule_set_version",
        "article",
        "status",
        "source",
        "evidence_ref",
        "confidence",
        "confidence_label",
        "tree_sha256",
        "tree_dirty",
        "signed",
        "verdict",
    ]
    assert len(rows) == 1 + len(_ROWS)
    assert [r[3] for r in rows[1:]] == [r[0] for r in _ROWS]
    assert rows[2][7] == ""  # null confidence is an empty cell
    assert rows[1][1:3] == ["abc1234", "2026.10"]


def test_no_free_text_outside_the_embedded_artifact(tmp_path):
    src, _ = _signed(tmp_path)
    assert _MARKER in src.read_text(encoding="utf-8")
    pkg = json.loads(_export(src).stdout)
    assert _MARKER in json.dumps(pkg["artifact"])
    del pkg["artifact"]
    assert _MARKER not in json.dumps(pkg)
    assert _MARKER not in _export(src, "--format", "csv").stdout


def test_csv_system_id_formula_is_neutralised(tmp_path):
    src, _ = _signed(tmp_path, system_id='=HYPERLINK("x")')
    res = _export(src, "--format", "csv")
    rows = list(csv.reader(io.StringIO(res.stdout, newline="")))
    assert rows[1][0] == '\'=HYPERLINK("x")'
    assert all(not r[0].startswith("=") for r in rows[1:])


def test_unsigned_artifact_exports_with_signed_false(tmp_path):
    src = tmp_path / "unsigned.json"
    src.write_text(_artifact().model_dump_json(), encoding="utf-8")
    res = _export(src)
    assert res.exit_code == 0, res.output
    pkg = json.loads(res.stdout)
    assert pkg["verification"]["signed"] is False
    assert pkg["verdict"]["result"] == "control_fail"  # exit 0 whatever the verdict


def test_gapless_artifact_exports_with_gaps_included_false(tmp_path):
    raw = json.loads(_artifact().model_dump_json())
    raw["gap_report"] = None
    src = tmp_path / "nogap.json"
    src.write_text(json.dumps(raw), encoding="utf-8")
    res = _export(src)
    assert res.exit_code == 0, res.output
    pkg = json.loads(res.stdout)
    jsonschema.validate(pkg, json.loads(_SCHEMA.read_text(encoding="utf-8")))
    assert pkg["gaps_included"] is False
    assert pkg["articles"] == []
    csv_res = _export(src, "--format", "csv")
    assert csv_res.exit_code == 0, csv_res.output
    assert len(list(csv.reader(io.StringIO(csv_res.stdout, newline="")))) == 1


def test_missing_gap_report_exits_2(tmp_path):
    """Legacy id kept so the recorded baseline still finds it; the old rule is gone.

    A missing gap report used to exit 2. It now exports, so this pins that it no
    longer exits 2 (the full contract is the gapless test above).
    """
    raw = json.loads(_artifact().model_dump_json())
    raw.pop("gap_report", None)
    src = tmp_path / "nogap.json"
    src.write_text(json.dumps(raw), encoding="utf-8")
    assert _export(src).exit_code == 0


def test_check_without_gaps_exports_gaps_included_false(tmp_path, monkeypatch):
    from opencomplai_cli import main
    from opencomplai_core.models import SystemManifest

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    monkeypatch.delenv("OPENCOMPLAI_VAULT_URL", raising=False)
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setattr(main, "_SIGNING_KEY", key_dir / "signing.key")
    manifest_file = tmp_path / "system-manifest.json"
    manifest_file.write_text(
        SystemManifest(
            system_id="export-sys",
            intended_purpose="customer support chatbot",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref="HEAD",
        ).model_dump_json(),
        encoding="utf-8",
    )

    checked = runner.invoke(app, ["check", "--manifest", str(manifest_file), "--sign"])
    assert checked.exit_code == 0, checked.output
    written = tmp_path / "compliance-artifact.json"
    assert json.loads(written.read_text(encoding="utf-8")).get("gap_report") is None

    embedded = tmp_path / "embedded.json"
    res = _export(written, "--artifact-out", str(embedded))
    assert res.exit_code == 0, res.output
    pkg = json.loads(res.stdout)
    assert pkg["gaps_included"] is False
    assert pkg["articles"] == []
    manifest_digest = "sha256:" + pkg["identity"]["manifest_sha256"]
    assert manifest_digest in pkg["evidence_hashes"]

    ok = runner.invoke(
        app,
        [
            "verify",
            str(embedded),
            "--kind",
            "artifact",
            "--pub-key",
            str(key_dir / "signing.pub"),
        ],
    )
    assert ok.exit_code == 0, ok.output


def test_bad_input_exits_2(tmp_path):
    assert _export(tmp_path / "missing.json").exit_code == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert _export(bad).exit_code == 2
    other = tmp_path / "other.json"
    other.write_text('{"hello": "world"}', encoding="utf-8")
    assert _export(other).exit_code == 2


def test_out_writes_file_and_stdout_is_empty(tmp_path):
    src, _ = _signed(tmp_path)
    out = tmp_path / "evidence-package.json"
    res = _export(src, "--out", str(out))
    assert res.exit_code == 0, res.output
    assert res.stdout == ""
    data = out.read_bytes()
    assert b"\r" not in data
    assert data.endswith(b"}\n")
    assert json.loads(data)["identity"]["system_id"] == "sys-1"


def test_export_is_registered_and_documented():
    assert "export" in {c.name for c in app.registered_commands}
    root = Path(__file__).resolve().parents[3]
    assert (root / "docs" / "src" / "cli" / "export.md").is_file()
