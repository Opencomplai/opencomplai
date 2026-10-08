"""Guard the signing/key claims in the docs (SU-3c). Plain substring checks."""

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[3] / "docs" / "src"


def _t(rel: str) -> str:
    return (DOCS / rel).read_text(encoding="utf-8")


def test_ci_guide_states_key_requirement_and_keyless_flag():
    t = _t("guides/ci-integration.md")
    block = t.split("## Any other CI platform", 1)[1].split("## Scope", 1)[0]
    assert "SIGNING_KEY_PRIVATE" in block
    assert "signing.key" in block
    assert re.search(r"exits `2`", block)
    assert "opencomplai check --sign-if-available" in block


def test_configuration_signing_rows():
    t = _t("deployment/configuration.md")
    assert "| `SIGNING_KEY_PRIVATE`" in t
    assert "~/.opencomplai/signing.key" in t
    assert "--sign-if-available" in t


def test_data_model_states_signature_survives_push():
    t = _t("architecture/data-model.md")
    sec = t.split("What the signature covers", 1)[1]
    for word in ("timestamp", "policy_bundle_version", "commit_ref", "survives push"):
        assert word in sec[:800]


def test_troubleshooting_pages_cover_keyless_sign():
    ci = _t("troubleshooting/common-issues.md")
    assert re.search(r"--sign` exits 2", ci)
    assert "unsigned" in ci
    assert "SIGNING_KEY_PRIVATE" in ci
    dbg = _t("troubleshooting/debugging.md")
    assert "--sign-if-available" in dbg
    assert "did not survive push" in dbg
    faq = _t("troubleshooting/faq.md")
    assert "sign in CI without a key file" in faq
    assert "SIGNING_KEY_PRIVATE" in faq
    assert "--sign-if-available" in faq


def test_no_page_documents_local_signing_key_path_as_artifact_key():
    for p in DOCS.rglob("*.md"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if "LOCAL_SIGNING_KEY_PATH" in line and re.search(
                r"signed status artifacts|signs? (status )?artifacts", line
            ):
                assert re.search(
                    r"not used for (artifact|status)|(does not|doesn't) sign (status )?artifacts",
                    line,
                ), f"{p}: {line}"


# --- Shipped files outside docs/src (SU-G5n) ---------------------------------

ROOT = DOCS.parents[1]
SHIPPED = (
    "README.md",
    "packages/*/README.md",
    "services/*/README.md",
    "integrations/*/README.md",
    "infra/compose/docker-compose.yml",
    "packages/*/src/**/*.py",
    "services/*/src/**/*.py",
)
BLOCK_EXEMPT = re.compile(
    r"no longer|not used|not read|does not|doesn't|never|ignored|signs nothing",
    re.I,
)
LINE_EXEMPT = re.compile(r"legacy|no longer|never|ignored|not read", re.I)
SIGN_WORD = re.compile(r"\b(signs?|signed|signing)\b|hmac|symmetric", re.I)
HMAC_CLAIM = re.compile(r"falls? back to HMAC|HMAC signature|hmac-local", re.I)


def _units(text: str):
    run: list[str] = []
    for line in text.splitlines():
        if line.startswith("|"):
            if run:
                yield "\n".join(run)
                run = []
            yield line
        elif line.strip():
            run.append(line)
        elif run:
            yield "\n".join(run)
            run = []
    if run:
        yield "\n".join(run)


def shipped_claims(text: str) -> list[str]:
    found: list[str] = []
    for unit in _units(text):
        if (
            "LOCAL_SIGNING_KEY_PATH" in unit
            and SIGN_WORD.search(unit)
            and not BLOCK_EXEMPT.search(unit)
        ):
            found.append(unit)
    for line in text.splitlines():
        if LINE_EXEMPT.search(line):
            continue
        if HMAC_CLAIM.search(line) or (
            "LOG_RETENTION_DAYS" in line and re.search(r"record|dossier", line, re.I)
        ):
            found.append(line)
    return list(dict.fromkeys(found))


def test_shipped_files_make_no_hmac_or_retention_claim():
    files = sorted({p for g in SHIPPED for p in ROOT.glob(g)})
    rel = {p.relative_to(ROOT).as_posix() for p in files}
    for edited in (
        "services/doc-generator/README.md",
        "packages/core/src/opencomplai_core/signing.py",
        "packages/cli/src/opencomplai_cli/publish.py",
    ):
        assert edited in rel
    assert not [p for p in files if p.name.startswith(".env")]
    bad = [
        f"{p.relative_to(ROOT).as_posix()}: {c}"
        for p in files
        for c in shipped_claims(p.read_text(encoding="utf-8"))
    ]
    assert not bad, "\n".join(bad)


def test_claim_scanner_flags_the_original_wordings():
    originals = [
        "| `LOCAL_SIGNING_KEY_PATH` | unset | Path to a symmetric key. Used for an "
        "HMAC signature only when `DOSSIER_SIGNING_KEY_PATH` is not set. With "
        "neither variable the dossier is unsigned. |",
        "| `LOG_RETENTION_DAYS` | `2555` | Retention period recorded in the "
        "dossier's record-keeping section. |",
        "that Pro/Enterprise dossiers use; OSS falls back to HMAC (no public key",
        "``cli:unsigned`` in OSS default mode, ``cli:hmac-local`` /",
    ]
    for text in originals:
        assert shipped_claims(text), text
    corrected = [
        "| `LOCAL_SIGNING_KEY_PATH` | unset | Ignored: it signs nothing. Dossiers "
        "are signed only with an Ed25519 key (`DOSSIER_SIGNING_KEY_PATH` or "
        "`SIGNING_KEY_PRIVATE`) and are otherwise unsigned; with only this "
        "variable set, generation warns and the dossier is unsigned. |",
        "| `LOG_RETENTION_DAYS` | n/a | Not read. The record-keeping section of "
        "the dossier holds only what the manifest's `record_keeping` block "
        "declares. |",
        "bundle domain signs through; there is no symmetric fallback, and a "
        "dossier with no Ed25519 key stays unsigned.",
        "dossier file passes through, a legacy ``cli:hmac-local`` in an old",
    ]
    for text in corrected:
        assert not shipped_claims(text), text


def test_doc_generator_readme_and_compose_match_signing_code():
    rows = {
        line.split("`")[1]: line
        for line in (ROOT / "services/doc-generator/README.md")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.startswith("| `")
    }
    assert "must still be set" not in rows["SIGNING_KEY_PRIVATE"]
    assert "Ignored" in rows["LOCAL_SIGNING_KEY_PATH"]
    assert "Not read" in rows["LOG_RETENTION_DAYS"]
    compose = (ROOT / "infra/compose/docker-compose.yml").read_text(encoding="utf-8")
    assert "SIGNING_KEY" not in compose
