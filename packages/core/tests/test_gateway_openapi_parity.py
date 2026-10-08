"""
The routes gateway-api registers, ``services/gateway-api/openapi.yaml``,
``docs/src/api/rest-api.md`` and the quick reference in
``docs/src/guides/api-basics.md`` must describe the same endpoints, in both
directions: a route nobody documented fails, and so does documentation left
behind for a route that is gone.

They drifted: the gateway routed 25 endpoints while the spec listed 9 and the
REST reference 7, so integrators were reading a contract that omitted most of
the surface (ledger verification, the HITL queue, dossier retrieval, badges,
Pro ingest, the portfolio).

Like ``test_version_parity.py`` this reads the sources as text. The gateway is
TypeScript and Node is not needed here: routes are extracted from
``routes/*.ts`` with the ``/v1`` prefix taken from ``routes/index.ts``, so
adding a route without documenting it fails this test in the Python CI jobs.
A plugin the extractor cannot parse raises instead of being skipped.

The real-tree tests skip when the gateway sources or a docs page are absent
from a checkout; the self-tests below run everywhere.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_REPO = Path(__file__).resolve().parents[3]
_GATEWAY = _REPO / "services" / "gateway-api"
_MD_PAGES = {
    "rest-api.md": _REPO / "docs" / "src" / "api" / "rest-api.md",
    "api-basics.md": _REPO / "docs" / "src" / "guides" / "api-basics.md",
}

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
_METHOD = "GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS"

# app.register(fooRoutes) / app.register(fooRoutes, { prefix: '/v1' })
_REGISTER = re.compile(
    r"\b\w+\.register\(\s*(\w+)\s*(?:,\s*\{\s*prefix:\s*['\"]([^'\"]*)['\"]\s*\})?\s*\)"
)
# export const fooRoutes: FastifyPluginAsync = async (app): Promise<void> => {
# The second group is the name the plugin gives its Fastify instance.
_PLUGIN = re.compile(
    r"export const (\w+)\s*:\s*FastifyPluginAsync\s*=\s*async\s*\(\s*(\w+)"
)
# Markdown: a `## `METHOD /path`` heading, or a summary-table row whose first
# two cells are the method and the path.
_MD_HEADING = re.compile(rf"^#{{1,6}}\s+`?({_METHOD})\s+(/\S*?)`?\s*$", re.M)
_MD_ROW = re.compile(rf"^\|\s*`?({_METHOD})`?\s*\|\s*`?(/[^`\s|]*)`?\s*\|", re.M)

Route = tuple[str, str]  # (METHOD, path with {param} placeholders)


def _normalise(path: str) -> str:
    return re.sub(r":(\w+)", r"{\1}", path)


def gateway_routes(routes_dir: Path) -> set[Route]:
    """Every (method, path) the gateway registers, /v1 prefix applied."""
    index = (routes_dir / "index.ts").read_text(encoding="utf-8")
    prefixes = dict(_REGISTER.findall(index))
    if len(prefixes) != index.count(".register("):
        raise AssertionError(
            "routes/index.ts has a .register(...) call this test cannot parse"
        )

    plugin_files: dict[str, tuple[Path, str]] = {}
    for ts in sorted(routes_dir.glob("*.ts")):
        if ts.name != "index.ts":
            for name, instance in _PLUGIN.findall(ts.read_text(encoding="utf-8")):
                plugin_files[name] = (ts, instance)

    routed: set[Route] = set()
    for plugin, prefix in prefixes.items():
        if plugin not in plugin_files:
            raise AssertionError(
                f"routes/index.ts registers {plugin!r} but no routes/*.ts exports it "
                f"as 'export const {plugin}: FastifyPluginAsync = async (<instance>)', "
                "the only plugin style this test can parse"
            )
        ts, instance = plugin_files[plugin]
        src = ts.read_text(encoding="utf-8")
        # Routes on the plugin's own instance, whatever it is called.
        call = rf"\b{re.escape(instance)}\.(get|post|put|patch|delete|head|options|all|route)"
        found = re.findall(
            rf"\b{re.escape(instance)}\.(get|post|put|patch|delete)\s*(?:<[^()]*?>)?"
            r"\s*\(\s*(['\"])(/[^'\"]*)\2",
            src,
        )
        if not found:
            raise AssertionError(
                f"{ts.name}: plugin {plugin!r} yields no routes this test can parse "
                f"(expected {instance}.<verb>('/path', ...) calls)"
            )
        if len(found) != len(re.findall(rf"{call}\s*[<(]", src)):
            raise AssertionError(
                f"{ts.name} registers a route in a style this test cannot parse "
                f"(expected {instance}.<verb>('/path', ...))"
            )
        for verb, _quote, path in found:
            routed.add((verb.upper(), _normalise(prefix + path)))
    return routed


def openapi_routes(spec: dict) -> set[Route]:
    return {
        (method.upper(), path)
        for path, item in spec["paths"].items()
        for method in item
        if method in _HTTP_METHODS
    }


def _fmt(routes: set[Route]) -> str:
    return ", ".join(f"{m} {p}" for m, p in sorted(routes, key=lambda r: (r[1], r[0])))


def diff_message(routed: set[Route], documented: set[Route], doc_name: str) -> str:
    """Which routes are missing on which side; empty when the sets are equal."""
    lines = []
    if routed - documented:
        lines.append(f"routed but missing from {doc_name}: {_fmt(routed - documented)}")
    if documented - routed:
        lines.append(f"in {doc_name} but not routed: {_fmt(documented - routed)}")
    return "\n".join(lines)


def _md_endpoints(md: str) -> list[tuple[Route, str]]:
    """Every `METHOD /path` heading and summary row, with the text it came from."""
    return [
        ((m.group(1), m.group(2)), m.group(0).strip())
        for pattern in (_MD_HEADING, _MD_ROW)
        for m in pattern.finditer(md)
    ]


def undocumented_in_markdown(md: str, routed: set[Route]) -> set[Route]:
    """Routes with neither a `METHOD /path` heading nor a table row."""
    return routed - {route for route, _ in _md_endpoints(md)}


def stale_in_markdown(md: str, routed: set[Route]) -> list[str]:
    """The headings and rows that name a `METHOD /path` the gateway does not route."""
    return [text for route, text in _md_endpoints(md) if route not in routed]


# ---------------------------------------------------------------------------
# Real tree
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def routed() -> set[Route]:
    if not (_GATEWAY / "src" / "routes").is_dir():
        pytest.skip("services/gateway-api not present in this checkout")
    found = gateway_routes(_GATEWAY / "src" / "routes")
    assert found, "extracted no routes; the extractor is broken, not the docs"
    return found


def test_openapi_matches_routed_surface(routed: set[Route]) -> None:
    spec = yaml.safe_load((_GATEWAY / "openapi.yaml").read_text(encoding="utf-8"))
    message = diff_message(routed, openapi_routes(spec), "openapi.yaml")
    assert not message, message


@pytest.mark.parametrize("page", _MD_PAGES)
def test_markdown_documents_every_route(routed: set[Route], page: str) -> None:
    if not _MD_PAGES[page].is_file():
        pytest.skip(f"{page} not present in this checkout")
    missing = undocumented_in_markdown(
        _MD_PAGES[page].read_text(encoding="utf-8"), routed
    )
    assert not missing, (
        f"routed but not documented in {page} (heading or summary-table row with "
        f"method and path): {_fmt(missing)}"
    )


@pytest.mark.parametrize("page", _MD_PAGES)
def test_markdown_documents_no_unrouted_route(routed: set[Route], page: str) -> None:
    if not _MD_PAGES[page].is_file():
        pytest.skip(f"{page} not present in this checkout")
    stale = stale_in_markdown(_MD_PAGES[page].read_text(encoding="utf-8"), routed)
    assert not stale, (
        f"{page} documents routes the gateway does not register; remove or fix: "
        + "; ".join(stale)
    )


# ---------------------------------------------------------------------------
# Self-tests: the comparison must actually fail when a route goes missing
# ---------------------------------------------------------------------------


def _mini_gateway(tmp_path: Path, files: dict[str, str]) -> Path:
    routes = tmp_path / "routes"
    routes.mkdir()
    for name, body in files.items():
        (routes / name).write_text(body, encoding="utf-8")
    return routes


_MINI_INDEX = """
export async function registerRoutes(app: FastifyInstance): Promise<void> {
  await app.register(healthRoutes);
  await app.register(docsRoutes, { prefix: '/v1' });
}
"""
_MINI_HEALTH = """
export const healthRoutes: FastifyPluginAsync = async (app) => {
  app.get('/health', async () => ({ status: 'ok' }));
};
"""
_MINI_DOCS = """
export const docsRoutes: FastifyPluginAsync = async (app) => {
  app.post('/docs/generate', async (req, reply) => {});
  app.get<{ Params: { dossier_id: string } }>(
    '/docs/:dossier_id',
    async (req, reply) => {},
  );
};
"""
_MINI_ROUTED = {
    ("GET", "/health"),
    ("POST", "/v1/docs/generate"),
    ("GET", "/v1/docs/{dossier_id}"),
}


def _mini_routes(tmp_path: Path, **overrides: str) -> Path:
    files = {"index.ts": _MINI_INDEX, "health.ts": _MINI_HEALTH, "docs.ts": _MINI_DOCS}
    return _mini_gateway(tmp_path, {**files, **overrides})


def test_extractor_applies_prefix_and_handles_both_call_styles(tmp_path: Path) -> None:
    assert gateway_routes(_mini_routes(tmp_path)) == _MINI_ROUTED


def test_extractor_follows_an_instance_that_is_not_named_app(tmp_path: Path) -> None:
    docs = """
export const docsRoutes: FastifyPluginAsync = async (fastify: FastifyInstance) => {
  fastify.post('/docs/generate', async (req, reply) => {});
  fastify.get('/docs/:dossier_id', async (req, reply) => {});
};
"""
    routes = _mini_routes(tmp_path, **{"docs.ts": docs})
    assert gateway_routes(routes) == _MINI_ROUTED


def test_extractor_rejects_a_route_style_it_cannot_parse(tmp_path: Path) -> None:
    routes = _mini_routes(
        tmp_path,
        **{
            "docs.ts": _MINI_DOCS.replace(
                "app.post('/docs/generate'",
                "app.route({ method: 'POST', url: '/docs/generate' }, ",
            )
        },
    )
    with pytest.raises(AssertionError, match="cannot parse"):
        gateway_routes(routes)


def test_extractor_rejects_a_plugin_it_cannot_parse(tmp_path: Path) -> None:
    # A function declaration, not 'export const x: FastifyPluginAsync = async (app)'.
    docs = """
export async function docsRoutes(app: FastifyInstance): Promise<void> {
  app.post('/docs/generate', async (req, reply) => {});
}
"""
    routes = _mini_routes(tmp_path, **{"docs.ts": docs})
    with pytest.raises(AssertionError, match="docsRoutes"):
        gateway_routes(routes)


def test_extractor_rejects_a_plugin_whose_routes_it_cannot_find(tmp_path: Path) -> None:
    # Routes registered on an alias of the instance would otherwise vanish.
    docs = """
export const docsRoutes: FastifyPluginAsync = async (app) => {
  const typed = app.withTypeProvider();
  typed.post('/docs/generate', async (req, reply) => {});
};
"""
    routes = _mini_routes(tmp_path, **{"docs.ts": docs})
    with pytest.raises(AssertionError, match=r"docsRoutes.*no routes"):
        gateway_routes(routes)


def test_diff_names_the_route_missing_from_openapi() -> None:
    spec = {
        "paths": {
            "/health": {"get": {}},
            "/v1/docs/generate": {"post": {}},
            "/v1/removed": {"get": {}, "parameters": []},
        }
    }
    message = diff_message(_MINI_ROUTED, openapi_routes(spec), "openapi.yaml")
    assert "routed but missing from openapi.yaml: GET /v1/docs/{dossier_id}" in message
    assert "in openapi.yaml but not routed: GET /v1/removed" in message


def test_diff_is_empty_when_spec_matches() -> None:
    spec = {
        "paths": {
            "/health": {"get": {}},
            "/v1/docs/generate": {"post": {}},
            "/v1/docs/{dossier_id}": {"get": {}},
        }
    }
    assert diff_message(_MINI_ROUTED, openapi_routes(spec), "openapi.yaml") == ""


def test_markdown_check_flags_a_route_with_no_heading_or_row() -> None:
    md = (
        "## `GET /health`\n\n"
        "| Method | Path |\n|---|---|\n"
        "| `POST` | `/v1/docs/generate` | doc-generator |\n"
        "Mentions GET /v1/docs/{dossier_id} only in prose.\n"
    )
    assert undocumented_in_markdown(md, _MINI_ROUTED) == {
        ("GET", "/v1/docs/{dossier_id}")
    }


def test_markdown_check_names_a_stale_heading_and_row() -> None:
    md = (
        "## `GET /health`\n\n"
        "## `DELETE /v1/docs/{dossier_id}`\n\n"
        "| Method | Path | Service |\n|---|---|---|\n"
        "| `POST` | `/v1/docs/generate` | doc-generator |\n"
        "| `GET` | `/v1/docs/{dossier_id}` | doc-generator |\n"
        "| `GET` | `/v1/removed` | doc-generator |\n"
    )
    stale = stale_in_markdown(md, _MINI_ROUTED)
    assert stale == [
        "## `DELETE /v1/docs/{dossier_id}`",
        "| `GET` | `/v1/removed` |",
    ]


def test_markdown_check_is_clean_when_pages_match() -> None:
    md = (
        "## `GET /health`\n\n"
        "| `POST` | `/v1/docs/generate` | doc-generator |\n"
        "| `GET` | `/v1/docs/{dossier_id}` | doc-generator |\n"
    )
    assert undocumented_in_markdown(md, _MINI_ROUTED) == set()
    assert stale_in_markdown(md, _MINI_ROUTED) == []
