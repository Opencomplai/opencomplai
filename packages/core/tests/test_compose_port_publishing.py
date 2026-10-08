"""
Which compose services publish a host port, and on which address.

``infra/compose/docker-compose.yml`` publishes exactly three ports: the gateway
(the stack's entry point, auth-gated, all interfaces) and the Prometheus and
Grafana operator UIs. Prometheus has no authentication and Grafana ships with
anonymous Viewer access and the stock admin login, so those two bind to
loopback unless ``OBSERVABILITY_BIND_ADDR`` is set to something else.

Like ``test_gateway_openapi_parity.py`` this reads the file as data and needs
neither Docker nor a running stack. ``${VAR:-default}`` is expanded here rather
than by Compose, so the resolver gets its own self-tests. The real-tree tests
skip when the compose file is absent; the self-tests run everywhere.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_REPO = Path(__file__).resolve().parents[3]
_COMPOSE = _REPO / "infra" / "compose" / "docker-compose.yml"
_CONFIGURATION_MD = _REPO / "docs" / "src" / "deployment" / "configuration.md"
_OBSERVABILITY_MD = _REPO / "docs" / "src" / "deployment" / "observability.md"

_BIND_VAR = "OBSERVABILITY_BIND_ADDR"
_OPERATOR_UIS = {"prometheus", "grafana"}
# Application ports. Anything else publishing a host port is a new exposure and
# has to be added here deliberately.
_EXPECTED_PUBLISHERS = {"gateway-api"} | _OPERATOR_UIS

_VAR = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")


def _expand(text: str, env: dict[str, str]) -> str:
    """``${VAR:-default}`` with Compose semantics: unset *or empty* takes the default."""
    return _VAR.sub(lambda m: env.get(m[1]) or (m[2] or ""), text)


def _parse(entry: object, env: dict[str, str]) -> tuple[str | None, str, str]:
    """Short-syntax port entry -> (host address or None, host port, container port)."""
    assert isinstance(entry, str), f"unsupported ports entry {entry!r}; extend _parse"
    parts = _expand(entry, env).split(":")
    assert len(parts) in (2, 3), f"unsupported ports entry {entry!r}; extend _parse"
    return (parts[0] if len(parts) == 3 else None, parts[-2], parts[-1])


def _published(
    compose: dict, env: dict[str, str]
) -> dict[str, list[tuple[str | None, str, str]]]:
    return {
        name: [_parse(p, env) for p in svc["ports"]]
        for name, svc in compose["services"].items()
        if svc.get("ports")
    }


def _host_networked(compose: dict) -> set[str]:
    """Services on the host network stack: every port they listen on is published."""
    return {
        name
        for name, svc in compose["services"].items()
        if svc.get("network_mode") == "host"
    }


@pytest.fixture(scope="module")
def compose() -> dict:
    if not _COMPOSE.is_file():
        pytest.skip("infra/compose/docker-compose.yml not present in this checkout")
    return yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))


# --- real tree ---------------------------------------------------------------


def test_operator_uis_bind_to_loopback_by_default(compose):
    published = _published(compose, env={})
    for name in _OPERATOR_UIS:
        assert [ip for ip, _, _ in published[name]] == ["127.0.0.1"], name


def test_bind_addr_is_an_explicit_opt_in_for_both_operator_uis(compose):
    published = _published(compose, env={_BIND_VAR: "0.0.0.0"})
    for name in _OPERATOR_UIS:
        assert [ip for ip, _, _ in published[name]] == ["0.0.0.0"], name


def test_host_port_variables_still_apply(compose):
    published = _published(
        compose, env={"PROMETHEUS_HOST_PORT": "19090", "GRAFANA_HOST_PORT": "13001"}
    )
    assert published["prometheus"] == [("127.0.0.1", "19090", "9090")]
    assert published["grafana"] == [("127.0.0.1", "13001", "3000")]


def test_only_the_gateway_and_operator_uis_publish_host_ports(compose):
    # Regression guard: postgres, redis and the internal services must stay
    # reachable only on the compose network.
    assert set(_published(compose, env={})) == _EXPECTED_PUBLISHERS
    # network_mode: host publishes every port with no `ports:` key at all.
    assert _host_networked(compose) == set()


def test_gateway_mapping_is_unchanged(compose):
    # Exposing the gateway is its purpose and it is auth-gated: no bind address.
    assert _published(compose, env={})["gateway-api"] == [(None, "8080", "8080")]
    assert compose["services"]["gateway-api"]["ports"] == ["${GATEWAY_PORT:-8080}:8080"]


def test_bind_addr_is_documented():
    if not _CONFIGURATION_MD.is_file() or not _OBSERVABILITY_MD.is_file():
        pytest.skip("deployment docs not present in this checkout")
    for doc in (_CONFIGURATION_MD, _OBSERVABILITY_MD):
        text = doc.read_text(encoding="utf-8")
        assert _BIND_VAR in text, doc.name
        assert "127.0.0.1" in text, doc.name


# --- resolver self-tests (run everywhere) ------------------------------------


def test_expand_uses_default_when_unset_or_empty_and_override_otherwise():
    assert _expand("${A:-x}", {}) == "x"
    assert _expand("${A:-x}", {"A": ""}) == "x"
    assert _expand("${A:-x}", {"A": "y"}) == "y"


def test_parse_short_syntax_forms():
    assert _parse("8080:80", {}) == (None, "8080", "80")
    assert _parse("${B:-127.0.0.1}:${P:-9090}:9090", {}) == (
        "127.0.0.1",
        "9090",
        "9090",
    )
    assert _parse("${B:-127.0.0.1}:${P:-9090}:9090", {"B": "0.0.0.0"}) == (
        "0.0.0.0",
        "9090",
        "9090",
    )


def test_parse_rejects_forms_it_cannot_read():
    with pytest.raises(AssertionError):
        _parse({"target": 80, "published": 8080}, {})
    with pytest.raises(AssertionError):
        _parse("80", {})


def test_published_flags_a_new_publisher():
    base = {
        "services": {
            "gateway-api": {"ports": ["8080:8080"]},
            "postgres": {"image": "x"},
        }
    }
    assert set(_published(base, {})) == {"gateway-api"}
    base["services"]["postgres"]["ports"] = ["5432:5432"]
    assert set(_published(base, {})) == {"gateway-api", "postgres"}


def test_host_networked_flags_network_mode_host():
    base = {"services": {"redis": {"image": "x"}, "app": {"network_mode": "bridge"}}}
    assert _host_networked(base) == set()
    base["services"]["redis"]["network_mode"] = "host"
    assert _host_networked(base) == {"redis"}
    assert set(_published(base, {})) == set()  # invisible to the ports check
