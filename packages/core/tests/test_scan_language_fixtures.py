"""
End-to-end scan of one tiny repository per ecosystem.

The manifest parsers and the JS/TS extractor each have unit tests, but nothing
ran ``run_scan`` over a Go, Rust, Maven, Gradle, Pipfile or JS/TS repository, so
a regression that disconnected an extractor from the detectors would leave every
unit test green. Each case here builds a real-shaped repository, declaring a
real AI SDK, and asserts the evidence comes out of ``run_scan``.

The repositories are written into ``tmp_path`` from inline strings on purpose:
each test is self-contained, with its input built at test time next to the
assertions that read it.

Known false negatives are recorded as strict xfails with the reason, so the day
one is fixed the test fails loudly and the marker gets deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from opencomplai_core.models import EvidenceKind, SignalCategory
from opencomplai_core.scan_engine import run_scan


@dataclass(frozen=True)
class Case:
    ecosystem: str
    #: ai_signals.json token the declared dependency must resolve to.
    token: str
    manifest: str
    source: str
    #: Whether the scanner has a source-level extractor for this language.
    source_extractor: bool
    #: path -> text for the repo declaring a real AI SDK.
    ai: dict[str, str]
    #: Same shape, with the SDK swapped for non-AI dependencies (negative control).
    #: One of them is a near-miss: its name holds the ``replicate`` / ``cohere``
    #: token only inside a longer word, which a looser matcher would flag.
    plain: dict[str, str]


CASES = [
    Case(
        ecosystem="go",
        token="openai",
        manifest="go.mod",
        source="cmd/app/main.go",
        source_extractor=False,
        ai={
            "go.mod": (
                "module example.com/app\n\ngo 1.22\n\n"
                "require github.com/sashabaranov/go-openai v1.26.0\n"
            ),
            "cmd/app/main.go": (
                "package main\n\n"
                "import (\n"
                '\t"context"\n\n'
                '\topenai "github.com/sashabaranov/go-openai"\n'
                ")\n\n"
                "func main() {\n"
                '\tclient := openai.NewClient("key")\n'
                "\t_, _ = client.CreateChatCompletion(context.Background(),"
                " openai.ChatCompletionRequest{Model: openai.GPT4o})\n"
                "}\n"
            ),
        },
        plain={
            "go.mod": (
                "module example.com/app\n\ngo 1.22\n\n"
                "require github.com/gin-gonic/gin v1.10.0\n"
                "require github.com/replicatedhq/troubleshoot v0.100.0\n"
            ),
            "cmd/app/main.go": (
                "package main\n\n"
                'import "github.com/gin-gonic/gin"\n\n'
                "func main() {\n\tgin.Default().Run()\n}\n"
            ),
        },
    ),
    Case(
        ecosystem="rust",
        token="openai",
        manifest="Cargo.toml",
        source="src/main.rs",
        source_extractor=False,
        ai={
            "Cargo.toml": (
                '[package]\nname = "app"\nversion = "0.1.0"\nedition = "2021"\n\n'
                '[dependencies]\nasync-openai = "0.23"\n'
                'tokio = { version = "1", features = ["full"] }\n'
            ),
            "src/main.rs": (
                "use async_openai::{types::CreateChatCompletionRequestArgs, Client};\n\n"
                "#[tokio::main]\n"
                "async fn main() {\n"
                "    let client = Client::new();\n"
                "    let request = CreateChatCompletionRequestArgs::default()\n"
                '        .model("gpt-4o")\n'
                "        .build()\n"
                "        .unwrap();\n"
                "    let _ = client.chat().create(request).await;\n"
                "}\n"
            ),
        },
        plain={
            "Cargo.toml": (
                '[package]\nname = "app"\nversion = "0.1.0"\nedition = "2021"\n\n'
                '[dependencies]\nserde = "1"\ncoherent-pool = "0.1"\n'
                'tokio = { version = "1", features = ["full"] }\n'
            ),
            "src/main.rs": (
                "use serde::Serialize;\n\n"
                "#[derive(Serialize)]\nstruct Ping {}\n\n"
                "fn main() {}\n"
            ),
        },
    ),
    Case(
        ecosystem="maven",
        token="openai",
        manifest="pom.xml",
        source="src/main/java/App.java",
        source_extractor=False,
        ai={
            "pom.xml": (
                "<project>\n"
                "  <modelVersion>4.0.0</modelVersion>\n"
                "  <groupId>com.example</groupId>\n"
                "  <artifactId>app</artifactId>\n"
                "  <version>1.0</version>\n"
                "  <dependencies>\n"
                "    <dependency>\n"
                "      <groupId>com.openai</groupId>\n"
                "      <artifactId>openai-java</artifactId>\n"
                "      <version>2.0.0</version>\n"
                "    </dependency>\n"
                "  </dependencies>\n"
                "</project>\n"
            ),
            "src/main/java/App.java": (
                "import com.openai.client.OpenAIClient;\n"
                "import com.openai.client.okhttp.OpenAIOkHttpClient;\n\n"
                "public class App {\n"
                "  public static void main(String[] args) {\n"
                "    OpenAIClient client = OpenAIOkHttpClient.fromEnv();\n"
                "    client.chat().completions().create(null);\n"
                "  }\n"
                "}\n"
            ),
        },
        plain={
            "pom.xml": (
                "<project>\n"
                "  <modelVersion>4.0.0</modelVersion>\n"
                "  <groupId>com.example</groupId>\n"
                "  <artifactId>app</artifactId>\n"
                "  <version>1.0</version>\n"
                "  <dependencies>\n"
                "    <dependency>\n"
                "      <groupId>org.springframework.boot</groupId>\n"
                "      <artifactId>spring-boot-starter-web</artifactId>\n"
                "      <version>3.3.0</version>\n"
                "    </dependency>\n"
                "    <dependency>\n"
                "      <groupId>com.example</groupId>\n"
                "      <artifactId>replicated-cache</artifactId>\n"
                "      <version>1.0</version>\n"
                "    </dependency>\n"
                "  </dependencies>\n"
                "</project>\n"
            ),
            "src/main/java/App.java": (
                "import org.springframework.boot.SpringApplication;\n\n"
                "public class App {\n"
                "  public static void main(String[] args) {\n"
                "    SpringApplication.run(App.class, args);\n"
                "  }\n"
                "}\n"
            ),
        },
    ),
    Case(
        ecosystem="gradle",
        token="google-cloud-aiplatform",
        manifest="build.gradle",
        source="src/main/java/App.java",
        source_extractor=False,
        ai={
            "build.gradle": (
                "plugins { id 'java' }\n\n"
                "dependencies {\n"
                "    implementation 'com.google.cloud:google-cloud-aiplatform:3.50.0'\n"
                "}\n"
            ),
            "src/main/java/App.java": (
                "import com.google.cloud.vertexai.VertexAI;\n"
                "import com.google.cloud.vertexai.generativeai.GenerativeModel;\n\n"
                "public class App {\n"
                "  public static void main(String[] args) throws Exception {\n"
                '    try (VertexAI vertex = new VertexAI("project", "europe-west4")) {\n'
                '      new GenerativeModel("gemini-1.5-pro", vertex)\n'
                '          .generateContent("hello");\n'
                "    }\n"
                "  }\n"
                "}\n"
            ),
        },
        plain={
            "build.gradle": (
                "plugins { id 'java' }\n\n"
                "dependencies {\n"
                "    implementation 'org.apache.commons:commons-lang3:3.14.0'\n"
                "    implementation 'com.example:replicated-cache:1.0'\n"
                "}\n"
            ),
            "src/main/java/App.java": (
                "import org.apache.commons.lang3.StringUtils;\n\n"
                "public class App {\n"
                "  public static void main(String[] args) {\n"
                '    StringUtils.capitalize("hello");\n'
                "  }\n"
                "}\n"
            ),
        },
    ),
    Case(
        ecosystem="pipfile",
        token="anthropic",
        manifest="Pipfile",
        source="app.py",
        source_extractor=True,
        ai={
            "Pipfile": (
                '[[source]]\nurl = "https://pypi.org/simple"\nverify_ssl = true\n'
                'name = "pypi"\n\n'
                '[packages]\nanthropic = "*"\n\n'
                '[requires]\npython_version = "3.11"\n'
            ),
            "app.py": (
                "import anthropic\n\n"
                "client = anthropic.Anthropic()\n"
                "client.messages.create(model='m', max_tokens=1, messages=[])\n"
            ),
        },
        plain={
            "Pipfile": (
                '[[source]]\nurl = "https://pypi.org/simple"\nverify_ssl = true\n'
                'name = "pypi"\n\n'
                '[packages]\nrequests = "*"\nreplicated = "*"\n\n'
                '[requires]\npython_version = "3.11"\n'
            ),
            "app.py": ("import requests\n\nrequests.get('https://example.com')\n"),
        },
    ),
    Case(
        ecosystem="typescript",
        token="openai",
        manifest="package.json",
        source="src/app.ts",
        source_extractor=True,
        ai={
            "package.json": (
                '{"name": "app", "dependencies": {"openai": "^4.52.0"}}\n'
            ),
            "src/app.ts": (
                'import OpenAI from "openai";\n\n'
                "const client = new OpenAI();\n"
                "export async function ask() {\n"
                "  return client.chat.completions.create("
                '{ model: "gpt-4o", messages: [] });\n'
                "}\n"
            ),
        },
        plain={
            "package.json": (
                '{"name": "app", "dependencies":'
                ' {"express": "^4.19.0", "replicated": "^1.0.0"}}\n'
            ),
            "src/app.ts": (
                'import express from "express";\n\nexport const app = express();\n'
            ),
        },
    ),
]


def _xfail(reason: str):
    """A known false negative. Strict: the day it is fixed, this test fails."""
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)


#: The scanner extracts source-level imports/callsites for Python and JS/TS only
#: (``extractors/ast.py`` -> ``_parse_python`` + ``collect_js``). Go, Rust and
#: Java sources are inventoried but never parsed, so only their manifests can
#: produce evidence. When a Go/Rust/Java extractor lands these XPASS and fail,
#: which is the prompt to delete the marker.
_NO_SOURCE_EXTRACTOR = (
    "no source-level import extractor for this language: "
    "scanner/extractors/ast.py handles Python and JS/TS only"
)
#: The gradle case has a second, independent reason to fail: it keeps failing
#: after a Java extractor lands (maven flips, gradle does not).
_VERTEX_JAVA_UNMAPPED = (
    "; and the Vertex AI Java packages (com.google.cloud.vertexai.*) match no "
    "ai_sdks token in ai_signals.json (the declared artifact maps to "
    "google-cloud-aiplatform), so it still fails once a Java extractor exists"
)
_TS_CALLSITE_GAP = (
    "TS/JS call sites never become AI_SDK evidence: extractors/javascript.py "
    "_CALLSITE emits bare method names (create, chat, completions, ...) and "
    "detectors/ast_usage.py matches them against ai_signals tokens, none of "
    "which is an ai_sdks token (only 'rerank' matches, as an embeddings signal). "
    "The Python case gets its CALLSITE from the constructor call "
    "anthropic.Anthropic(); JS `new OpenAI()` is not captured"
)
_CONFIG_GAP = (
    "scanner/extractors/config.py TEXT_EXTENSIONS has no .go/.rs/.java/.kt, so "
    "API-key and endpoint strings in those sources are never read (the same "
    "strings in a .ts file are)"
)
_LANGCHAIN_GAP = (
    "ai_signals.json lists 'langchain' and 'openai', but "
    "_signals.tokenize_identifier keeps 'langchain4j' / 'langchaingo' as one "
    "segment and splits 'open-ai' into 'open' and 'ai', so these package names "
    "match no token"
)

#: Declared dependency that is unmistakably an LLM library, yet scans clean.
LANGCHAIN_MANIFESTS = {
    "langchain4j-maven": (
        "pom.xml",
        "<project>\n"
        "  <dependencies>\n"
        "    <dependency>\n"
        "      <groupId>dev.langchain4j</groupId>\n"
        "      <artifactId>langchain4j</artifactId>\n"
        "      <version>0.35.0</version>\n"
        "    </dependency>\n"
        "    <dependency>\n"
        "      <groupId>dev.langchain4j</groupId>\n"
        "      <artifactId>langchain4j-open-ai</artifactId>\n"
        "      <version>0.35.0</version>\n"
        "    </dependency>\n"
        "  </dependencies>\n"
        "</project>\n",
    ),
    "langchain4j-gradle": (
        "build.gradle",
        "dependencies {\n"
        "    implementation 'dev.langchain4j:langchain4j:0.35.0'\n"
        "    implementation 'dev.langchain4j:langchain4j-open-ai:0.35.0'\n"
        "}\n",
    ),
    "langchaingo": (
        "go.mod",
        "module example.com/app\n\ngo 1.22\n\n"
        "require github.com/tmc/langchaingo v0.1.12\n",
    ),
}

#: The same OpenAI key name and endpoint, written in each language.
CONFIG_SOURCES = {
    "typescript": (
        "src/app.ts",
        "const key = process.env.OPENAI_API_KEY;\n"
        'const url = "https://api.openai.com/v1/chat/completions";\n',
    ),
    "go": (
        "cmd/app/main.go",
        "package main\n\n"
        'var key = os.Getenv("OPENAI_API_KEY")\n'
        'var url = "https://api.openai.com/v1/chat/completions"\n',
    ),
    "rust": (
        "src/main.rs",
        'fn main() {\n    let _key = std::env::var("OPENAI_API_KEY");\n'
        '    let _url = "https://api.openai.com/v1/chat/completions";\n}\n',
    ),
    "java": (
        "src/main/java/App.java",
        "class App {\n"
        '  String key = System.getenv("OPENAI_API_KEY");\n'
        '  String url = "https://api.openai.com/v1/chat/completions";\n'
        "}\n",
    ),
    "kotlin": (
        "src/main/kotlin/App.kt",
        'val key = System.getenv("OPENAI_API_KEY")\n'
        'val url = "https://api.openai.com/v1/chat/completions"\n',
    ),
}

#: build.gradle.kts and the lockfile parsers, each declaring one real AI SDK.
LOCKFILES = {
    "build.gradle.kts": (
        'plugins { java }\n\ndependencies {\n    implementation("com.openai:openai-java:2.0.0")\n}\n',
        "openai",
    ),
    "go.sum": (
        "github.com/sashabaranov/go-openai v1.26.0 h1:abc=\n"
        "github.com/sashabaranov/go-openai v1.26.0/go.mod h1:def=\n",
        "openai",
    ),
    "Cargo.lock": (
        'version = 3\n\n[[package]]\nname = "async-openai"\nversion = "0.23.0"\n',
        "openai",
    ),
    "package-lock.json": (
        '{"name": "app", "lockfileVersion": 3, "packages": {"": {"name": "app"},'
        ' "node_modules/openai": {"version": "4.52.0"}}}\n',
        "openai",
    ),
    "Pipfile.lock": (
        '{"_meta": {}, "default": {"anthropic": {"version": "==0.30.0"}},'
        ' "develop": {}}\n',
        "anthropic",
    ),
    "poetry.lock": (
        '[[package]]\nname = "anthropic"\nversion = "0.30.0"\n',
        "anthropic",
    ),
}


def _scan(tmp_path: Path, files: dict[str, str]):
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return run_scan(
        system_id="fixture-sys",
        commit_ref="HEAD",
        repo_root=tmp_path,
        declared_purpose="customer support chatbot",
    )


def _at(report, location_prefix: str):
    return [e for e in report.evidence if e.locations[0].startswith(location_prefix)]


def _ai_sdk_labels(report, kind: EvidenceKind, location_prefix: str) -> set[str]:
    return {
        e.token_label
        for e in _at(report, location_prefix)
        if e.evidence_kind is kind and e.category is SignalCategory.AI_SDK
    }


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.ecosystem)
def test_manifest_dependency_reaches_the_report(case: Case, tmp_path: Path):
    report = _scan(tmp_path, case.ai)

    assert report.detector_errors == []
    assert report.evidence, f"{case.ecosystem}: scan came back clean"
    assert _ai_sdk_labels(report, EvidenceKind.DEPENDENCY, f"{case.manifest}:") == {
        case.token
    }, report.evidence


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            c,
            id=c.ecosystem,
            marks=()
            if c.source_extractor
            else _xfail(
                _NO_SOURCE_EXTRACTOR
                + (_VERTEX_JAVA_UNMAPPED if c.ecosystem == "gradle" else "")
            ),
        )
        for c in CASES
    ],
)
def test_source_import_reaches_the_report(case: Case, tmp_path: Path):
    report = _scan(tmp_path, case.ai)

    assert _ai_sdk_labels(report, EvidenceKind.IMPORT, f"{case.source}:") == {
        case.token
    }, f"{case.ecosystem}: no import evidence\n{report.evidence}"


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            c,
            id=c.ecosystem,
            marks=_xfail(_TS_CALLSITE_GAP) if c.ecosystem == "typescript" else (),
        )
        for c in CASES
        if c.source_extractor
    ],
)
def test_source_callsite_reaches_the_report(case: Case, tmp_path: Path):
    report = _scan(tmp_path, case.ai)

    assert _ai_sdk_labels(report, EvidenceKind.CALLSITE, f"{case.source}:") == {
        case.token
    }, f"{case.ecosystem}: no callsite evidence\n{report.evidence}"


@pytest.mark.parametrize(
    "language",
    [
        pytest.param(
            lang, marks=() if lang == "typescript" else _xfail(_CONFIG_GAP), id=lang
        )
        for lang in CONFIG_SOURCES
    ],
)
def test_config_strings_in_source_reach_the_report(language: str, tmp_path: Path):
    path, text = CONFIG_SOURCES[language]
    report = _scan(tmp_path, {path: text})

    kinds = {e.evidence_kind for e in _at(report, f"{path}:")}
    assert {EvidenceKind.ENDPOINT, EvidenceKind.CONFIG_KEY} <= kinds, report.evidence


@pytest.mark.parametrize(
    ("manifest", "text"),
    [
        pytest.param(*v, id=k, marks=_xfail(_LANGCHAIN_GAP))
        for k, v in LANGCHAIN_MANIFESTS.items()
    ],
)
def test_langchain_dependency_reaches_the_report(
    manifest: str, text: str, tmp_path: Path
):
    report = _scan(tmp_path, {manifest: text})

    deps = [
        e
        for e in _at(report, f"{manifest}:")
        if e.evidence_kind is EvidenceKind.DEPENDENCY
    ]
    assert deps, f"{manifest}: scan came back clean\n{report.evidence}"


@pytest.mark.parametrize("name", LOCKFILES)
def test_kts_and_lockfile_dependency_reaches_the_report(name: str, tmp_path: Path):
    text, token = LOCKFILES[name]
    report = _scan(tmp_path, {name: text})

    assert report.detector_errors == []
    assert _ai_sdk_labels(report, EvidenceKind.DEPENDENCY, f"{name}:") == {token}, (
        report.evidence
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.ecosystem)
def test_non_ai_dependency_yields_no_evidence(case: Case, tmp_path: Path):
    """Negative control: same repo shape, SDK swapped for non-AI packages."""
    report = _scan(tmp_path, case.plain)

    assert report.detector_errors == []
    deps = [
        e
        for e in report.evidence
        if e.evidence_kind in (EvidenceKind.DEPENDENCY, EvidenceKind.LOCKFILE_PACKAGE)
    ]
    assert deps == [], "a non-AI or near-miss dependency was flagged"
    assert report.evidence == []
