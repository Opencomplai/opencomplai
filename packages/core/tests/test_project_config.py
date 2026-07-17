"""Tests for opencomplai.yaml project config loading (opencomplai.yaml, 3.5)."""

from opencomplai_core.project_config import (
    ProjectConfig,
    apply_project_config_defaults,
    find_project_config,
    load_project_config,
)


def test_find_project_config_returns_none_when_absent(tmp_path):
    assert find_project_config(tmp_path) is None


def test_find_project_config_finds_file(tmp_path):
    (tmp_path / "opencomplai.yaml").write_text("scan:\n  fail_on: major\n", encoding="utf-8")
    found = find_project_config(tmp_path)
    assert found is not None
    assert found.name == "opencomplai.yaml"


def test_load_project_config_parses_scan_section(tmp_path):
    config_file = tmp_path / "opencomplai.yaml"
    config_file.write_text(
        "scan:\n"
        "  fail_on: major\n"
        "  framework_detectors: true\n"
        "  allowlisted_categories:\n"
        "    - biometric\n",
        encoding="utf-8",
    )
    config = load_project_config(config_file)
    assert config.scan_fail_on == "major"
    assert config.scan_framework_detectors is True
    assert config.allowlisted_categories == ["biometric"]


def test_load_project_config_parses_eval_section(tmp_path):
    config_file = tmp_path / "opencomplai.yaml"
    config_file.write_text(
        "eval:\n  threshold_overrides:\n    bias: 0.9\n    safety: 0.95\n",
        encoding="utf-8",
    )
    config = load_project_config(config_file)
    assert config.eval_threshold_overrides == {"bias": 0.9, "safety": 0.95}


def test_load_project_config_handles_empty_file(tmp_path):
    config_file = tmp_path / "opencomplai.yaml"
    config_file.write_text("", encoding="utf-8")
    config = load_project_config(config_file)
    assert config == ProjectConfig()


def test_apply_defaults_uses_config_when_cli_not_explicit():
    config = ProjectConfig(scan_fail_on="major", scan_framework_detectors=True)
    fail_on, framework_detectors = apply_project_config_defaults(
        config,
        cli_fail_on_was_explicit=False,
        current_fail_on="none",
        cli_framework_detectors_was_explicit=False,
        current_framework_detectors=False,
    )
    assert fail_on == "major"
    assert framework_detectors is True


def test_apply_defaults_explicit_cli_flag_overrides_config():
    config = ProjectConfig(scan_fail_on="major", scan_framework_detectors=True)
    fail_on, framework_detectors = apply_project_config_defaults(
        config,
        cli_fail_on_was_explicit=True,
        current_fail_on="critical",
        cli_framework_detectors_was_explicit=True,
        current_framework_detectors=False,
    )
    assert fail_on == "critical"
    assert framework_detectors is False


def test_apply_defaults_with_no_config_is_a_no_op():
    fail_on, framework_detectors = apply_project_config_defaults(
        None,
        cli_fail_on_was_explicit=False,
        current_fail_on="none",
        cli_framework_detectors_was_explicit=False,
        current_framework_detectors=False,
    )
    assert fail_on == "none"
    assert framework_detectors is False
