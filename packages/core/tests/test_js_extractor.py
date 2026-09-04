"""
JS/TS import and callsite extraction (SCAN-COVERAGE, finding 83).

AST detection was Python-only, so a TypeScript service calling an AI provider
produced no import or callsite evidence at all — a false negative in the most
common non-Python stack for AI application code.

The extractor is regexes, not a parser, which is a deliberate bound (a real
JS/TS parser is a large dependency for a tool that runs over untrusted
repository content). These tests pin both what that buys and what it costs.
"""

from __future__ import annotations

import pytest
from opencomplai_core.models import EvidenceScope
from opencomplai_core.scanner.extractors.javascript import parse_js_source


def imports_of(source: str) -> set[str]:
    imports, _ = parse_js_source(source, "app.ts", EvidenceScope.PROD)
    return {i.module for i in imports}


def callsites_of(source: str) -> set[str]:
    _, calls = parse_js_source(source, "app.ts", EvidenceScope.PROD)
    return {c.name for c in calls}


@pytest.mark.parametrize(
    "source",
    [
        'import OpenAI from "openai";',
        'import { OpenAI } from "openai";',
        'import * as sdk from "openai";',
        'import "openai";',
        'const OpenAI = require("openai");',
        'const mod = await import("openai");',
        'export { OpenAI } from "openai";',
    ],
)
def test_every_import_form_is_detected(source: str):
    assert "openai" in imports_of(source)


def test_scoped_packages_keep_both_segments():
    # "@anthropic-ai" alone would be a scope, not a package.
    assert "@anthropic-ai/sdk" in imports_of(
        'import Anthropic from "@anthropic-ai/sdk";'
    )


def test_deep_import_is_reduced_to_the_package():
    assert imports_of('import { chat } from "openai/resources/chat";') == {"openai"}
    assert imports_of('import x from "@anthropic-ai/sdk/resources";') == {
        "@anthropic-ai/sdk"
    }


def test_relative_and_builtin_specifiers_are_not_packages():
    source = """
        import a from "./local";
        import b from "../shared/util";
        import c from "/abs/path";
        import fs from "node:fs";
    """

    assert imports_of(source) == set()


def test_commented_out_imports_are_not_evidence():
    source = """
        // import OpenAI from "openai";
        /* import Anthropic from "@anthropic-ai/sdk"; */
        import cohere from "cohere-ai";
    """

    found = imports_of(source)

    # The Python AST extractor cannot see commented code; this must not be
    # looser than the thing it mirrors.
    assert found == {"cohere-ai"}


@pytest.mark.parametrize(
    "provider",
    [
        "cohere-ai",
        "@mistralai/mistralai",
        "groq-sdk",
        "replicate",
        "@google/generative-ai",
    ],
)
def test_providers_beyond_openai_are_detected(provider: str):
    """The regexes this replaces covered only a handful of providers."""
    assert provider in imports_of(f'import x from "{provider}";')


def test_one_import_statement_counts_once():
    imports, _ = parse_js_source(
        'import OpenAI from "openai";', "app.ts", EvidenceScope.PROD
    )

    # The bare-import and import-from patterns can both match one statement.
    assert len(imports) == 1


def test_multiple_imports_are_each_located():
    imports, _ = parse_js_source(
        'import a from "openai";\nimport b from "cohere-ai";\n',
        "app.ts",
        EvidenceScope.PROD,
    )

    assert {i.location for i in imports} == {"app.ts:1", "app.ts:2"}


@pytest.mark.parametrize(
    "call",
    [
        "openai.chat.completions.create({})",
        "client.messages.create({})",
        "model.generateContent(prompt)",
        "cohere.embed({})",
        "bedrock.invokeModel({})",
        "replicate.run('owner/model')",
        "deepgram.transcribe(audio)",
        "cohere.rerank({})",
    ],
)
def test_model_invocation_callsites_are_detected(call: str):
    assert callsites_of(call)


def test_callsites_record_their_line():
    _, calls = parse_js_source(
        "const a = 1;\nopenai.chat.completions.create({});\n",
        "app.ts",
        EvidenceScope.PROD,
    )

    assert calls[0].location == "app.ts:2"


def test_scope_is_propagated():
    imports, calls = parse_js_source(
        'import x from "openai";\nx.create({});\n', "t.ts", EvidenceScope.TEST
    )

    assert imports[0].scope is EvidenceScope.TEST
    assert calls[0].scope is EvidenceScope.TEST


def test_computed_imports_are_a_known_blind_spot():
    """
    Documented limitation, asserted so it is a choice rather than a surprise:
    a specifier that is not a literal cannot be known without evaluating the
    program, and no cheaper approach sees it either.
    """
    assert imports_of("const mod = await import(someVariable);") == set()


def test_empty_and_garbage_input_are_safe():
    assert imports_of("") == set()
    assert callsites_of("") == set()
    assert imports_of("}{ not javascript (((") == set()
