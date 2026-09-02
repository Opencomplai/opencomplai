"""
Multi-ecosystem manifest parsing (SCAN-COVERAGE, finding 82).

``MANIFEST_FILES`` has always listed go.mod, Cargo.toml, pom.xml, build.gradle
and Pipfile, and ``AiDependencyDetector`` has always claimed java/go/rust
support — but ``extract_manifest_features`` only branched on
requirements/package.json/pyproject, so every other manifest yielded **zero
packages**. A Go or Rust service using an AI SDK produced no dependency
evidence at all, and the scan reported clean for the same reason a genuinely
AI-free repository does.

These tests use real AI SDK coordinates throughout, because "does an AI
dependency in this ecosystem produce evidence" is the actual question.
"""

from __future__ import annotations

import pytest
from opencomplai_core.models import EvidenceScope
from opencomplai_core.scanner.extractors.manifests import (
    _parse_cargo_lock,
    _parse_cargo_toml,
    _parse_go_mod,
    _parse_go_sum,
    _parse_gradle,
    _parse_json_lock,
    _parse_pipfile,
    _parse_pom_xml,
)


def names(packages) -> set[str]:
    return {p.name for p in packages}


def parse(fn, text: str) -> set[str]:
    return names(fn(text, "manifest", EvidenceScope.PROD, "test"))


# --- Go --------------------------------------------------------------------


def test_go_mod_block_form():
    found = parse(
        _parse_go_mod,
        """
        module example.com/app

        go 1.22

        require (
            github.com/sashabaranov/go-openai v1.26.0
            github.com/google/uuid v1.6.0 // indirect
        )
        """,
    )

    assert "github.com/sashabaranov/go-openai" in found
    assert "github.com/google/uuid" in found


def test_go_mod_single_line_form():
    found = parse(_parse_go_mod, "require github.com/sashabaranov/go-openai v1.26.0\n")

    assert found == {"github.com/sashabaranov/go-openai"}


def test_go_mod_ignores_directives_and_comments():
    found = parse(
        _parse_go_mod,
        """
        module example.com/app
        go 1.22
        toolchain go1.22.0
        // github.com/commented/out v1.0.0
        """,
    )

    # "go 1.22" and "toolchain" are directives, not modules. The module line is
    # excluded too: it names this repo, not a dependency.
    assert "go" not in found
    assert "toolchain" not in found
    assert "github.com/commented/out" not in found


def test_go_sum_reports_each_module_once():
    found = _parse_go_sum(
        "github.com/sashabaranov/go-openai v1.26.0 h1:abc=\n"
        "github.com/sashabaranov/go-openai v1.26.0/go.mod h1:def=\n",
        "go.sum",
        EvidenceScope.PROD,
        "go-sum",
    )

    assert names(found) == {"github.com/sashabaranov/go-openai"}
    assert len(found) == 1


# --- Rust ------------------------------------------------------------------


def test_cargo_toml_reads_dependency_tables_only():
    found = parse(
        _parse_cargo_toml,
        """
        [package]
        name = "my-crate"
        edition = "2021"

        [dependencies]
        async-openai = "0.23"
        serde = { version = "1", features = ["derive"] }

        [dev-dependencies]
        tokio-test = "0.4"
        """,
    )

    assert "async-openai" in found
    assert "tokio-test" in found
    # [package] keys are metadata, not crates.
    assert "edition" not in found
    assert "my-crate" not in found


def test_cargo_toml_handles_a_dependency_subtable():
    found = parse(
        _parse_cargo_toml,
        """
        [dependencies.async-openai]
        version = "0.23"
        """,
    )

    assert "async-openai" in found
    # `version` is a key of the crate's table, not a crate.
    assert "version" not in found


def test_cargo_lock_reads_package_blocks():
    found = parse(
        _parse_cargo_lock,
        """
        [[package]]
        name = "async-openai"
        version = "0.23.0"

        [[package]]
        name = "tokio"
        version = "1.38.0"
        """,
    )

    assert found == {"async-openai", "tokio"}


# --- Java ------------------------------------------------------------------


def test_pom_xml_reads_group_and_artifact():
    found = parse(
        _parse_pom_xml,
        """
        <project>
          <dependencies>
            <dependency>
              <groupId>dev.langchain4j</groupId>
              <artifactId>langchain4j-open-ai</artifactId>
              <version>0.33.0</version>
            </dependency>
          </dependencies>
        </project>
        """,
    )

    assert "dev.langchain4j:langchain4j-open-ai" in found


def test_pom_xml_ignores_non_dependency_elements():
    found = parse(
        _parse_pom_xml,
        """
        <project>
          <groupId>com.example</groupId>
          <artifactId>my-app</artifactId>
        </project>
        """,
    )

    # These identify the project itself, not a dependency of it.
    assert found == set()


def test_pom_xml_does_not_expand_entities():
    """
    Parsed with a regex rather than an XML parser because this runs over
    attacker-supplied repository content, and the stdlib XML parsers are
    vulnerable to entity-expansion. This must terminate, not allocate.
    """
    hostile = (
        '<!DOCTYPE t [<!ENTITY a "AAAA"><!ENTITY b "&a;&a;&a;&a;">]>'
        "<project><dependencies><dependency>"
        "<groupId>&b;</groupId><artifactId>x</artifactId>"
        "</dependency></dependencies></project>"
    )

    found = parse(_parse_pom_xml, hostile)

    # The entity is treated as literal text, never expanded.
    assert "&b;:x" in found


@pytest.mark.parametrize("filename", ["build.gradle", "build.gradle.kts"])
def test_gradle_reads_both_dsls(filename: str):
    groovy = """
        dependencies {
            implementation 'dev.langchain4j:langchain4j:0.33.0'
            testImplementation "org.junit.jupiter:junit-jupiter:5.10.0"
        }
    """
    kotlin = """
        dependencies {
            implementation("dev.langchain4j:langchain4j:0.33.0")
            testImplementation("org.junit.jupiter:junit-jupiter:5.10.0")
        }
    """
    found = parse(_parse_gradle, kotlin if filename.endswith(".kts") else groovy)

    assert "dev.langchain4j:langchain4j" in found
    assert "org.junit.jupiter:junit-jupiter" in found


def test_gradle_drops_the_version_so_one_dependency_is_one_package():
    found = parse(
        _parse_gradle,
        """
        dependencies {
            implementation 'dev.langchain4j:langchain4j:0.33.0'
            implementation 'dev.langchain4j:langchain4j:0.34.0'
        }
        """,
    )

    assert found == {"dev.langchain4j:langchain4j"}


# --- Python (Pipfile) and lockfiles ----------------------------------------


def test_pipfile_reads_package_tables_only():
    found = parse(
        _parse_pipfile,
        """
        [[source]]
        url = "https://pypi.org/simple"

        [packages]
        openai = "*"
        anthropic = ">=0.30"

        [dev-packages]
        pytest = "*"

        [requires]
        python_version = "3.11"
        """,
    )

    assert {"openai", "anthropic", "pytest"} <= found
    # [requires] and [[source]] are configuration, not packages.
    assert "python_version" not in found
    assert "url" not in found


def test_npm_v2_lockfile_uses_the_last_path_segment():
    found = parse(
        _parse_json_lock,
        """
        {
          "lockfileVersion": 3,
          "packages": {
            "": {"name": "root"},
            "node_modules/openai": {"version": "4.0.0"},
            "node_modules/@anthropic-ai/sdk": {"version": "0.27.0"}
          }
        }
        """,
    )

    assert "openai" in found
    assert "@anthropic-ai/sdk" in found
    # The empty key is the root project, not a dependency.
    assert "root" not in found


def test_npm_v1_lockfile_shape_is_also_handled():
    found = parse(
        _parse_json_lock,
        '{"lockfileVersion": 1, "dependencies": {"openai": {"version": "4.0.0"}}}',
    )

    assert found == {"openai"}


def test_malformed_lockfile_yields_nothing_rather_than_raising():
    assert parse(_parse_json_lock, "{not json") == set()
    assert parse(_parse_json_lock, "[]") == set()


def test_empty_input_is_safe_for_every_parser():
    for fn in (
        _parse_go_mod,
        _parse_go_sum,
        _parse_cargo_toml,
        _parse_cargo_lock,
        _parse_pom_xml,
        _parse_gradle,
        _parse_pipfile,
        _parse_json_lock,
    ):
        assert parse(fn, "") == set()


def test_locations_are_recorded_for_every_package():
    packages = _parse_cargo_toml(
        '[dependencies]\nasync-openai = "0.23"\n',
        "Cargo.toml",
        EvidenceScope.PROD,
        "cargo",
    )

    assert packages[0].location.startswith("Cargo.toml:")
