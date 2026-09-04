"""
JS/TS import and callsite extraction (SCAN-COVERAGE, finding 83).

AST import/callsite detection was Python-only. Every other language relied on
roughly fifteen hardcoded regexes covering a handful of providers, so a
TypeScript service calling Cohere, Mistral or Groq generated **no import or
callsite evidence at all** — a false negative in the single most common
non-Python stack for AI application code.

This is a regex extractor, not a parser, and that is a deliberate bound: a real
JS/TS parser is a large dependency to add to a security tool that must run over
untrusted repository content. Regexes cannot be induced to allocate unbounded
memory, and the goal here is "which AI modules does this file reach for",
not a faithful syntax tree. The cost is that computed imports
(``await import(someVariable)``) are invisible; those are rare in the code
paths this evidence is used for, and no cheaper approach sees them either.

Emits into the same ``ImportRef`` / ``CallsiteRef`` types the Python AST
extractor produces, so everything downstream — detectors, scoring, evidence —
treats a TypeScript import exactly like a Python one.
"""

from __future__ import annotations

import re
from pathlib import Path

from opencomplai_core.models import EvidenceScope
from opencomplai_core.scanner.feature_types import CallsiteRef, ImportRef

JS_LANGUAGES = frozenset({"javascript", "typescript"})

#: `import ... from "mod"` — the default, named, and namespace forms all end in
#: the same `from "..."`, so one pattern covers them.
_IMPORT_FROM = re.compile(r"""\bimport\b[^;\n]*?\bfrom\s*["']([^"']+)["']""")

#: Side-effect import: `import "mod";`
_IMPORT_BARE = re.compile(r"""\bimport\s*["']([^"']+)["']""")

#: `require("mod")` and dynamic `import("mod")`. Only literal specifiers —
#: a computed one is not knowable without evaluating the program.
_REQUIRE = re.compile(r"""\b(?:require|import)\s*\(\s*["']([^"']+)["']\s*\)""")

#: `export ... from "mod"` re-exports still create a dependency edge.
_EXPORT_FROM = re.compile(r"""\bexport\b[^;\n]*?\bfrom\s*["']([^"']+)["']""")

_IMPORT_PATTERNS = (_IMPORT_FROM, _IMPORT_BARE, _REQUIRE, _EXPORT_FROM)

#: Method calls that indicate model invocation rather than mere import.
#: Matched on the trailing member chain so `openai.chat.completions.create(...)`
#: and `client.messages.create(...)` both register.
_CALLSITE = re.compile(
    r"""\.(
        create|createMessage|createCompletion|createChatCompletion
        |chat|complete|completion|completions
        |generate|generateContent|generateText|generateObject|generateStream
        |embed|embeddings|embedContent|embedMany
        |invoke|invokeModel|predict|run|stream|streamText|streamObject
        |transcribe|synthesize|classify|rerank|moderate
    )\s*\(""",
    re.VERBOSE,
)

#: Comment stripping. Applied before matching so a commented-out import does
#: not become evidence — the Python AST extractor is immune to that by
#: construction, and this must not be looser than the thing it mirrors.
_LINE_COMMENT = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(text: str) -> str:
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", text))


def _module_root(specifier: str) -> str:
    """
    Reduce a specifier to its package name.

    ``openai/resources/chat`` -> ``openai``; ``@anthropic-ai/sdk/foo`` ->
    ``@anthropic-ai/sdk`` (a scoped package keeps two segments). Relative
    specifiers are not packages and are dropped by the caller.
    """
    parts = specifier.split("/")
    if specifier.startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def _is_relative(specifier: str) -> bool:
    return specifier.startswith((".", "/")) or specifier.startswith("node:")


def parse_js_source(
    text: str, rel_path: str, scope: EvidenceScope
) -> tuple[list[ImportRef], list[CallsiteRef]]:
    imports: list[ImportRef] = []
    callsites: list[CallsiteRef] = []
    seen_imports: set[tuple[str, int]] = set()

    cleaned = _strip_comments(text)

    for pattern in _IMPORT_PATTERNS:
        for match in pattern.finditer(cleaned):
            specifier = match.group(1).strip()
            if not specifier or _is_relative(specifier):
                continue
            module = _module_root(specifier)
            line = cleaned[: match.start()].count("\n") + 1
            # The bare-import and import-from patterns can both match one
            # statement; dedupe on (module, line) so it counts once.
            if (module, line) in seen_imports:
                continue
            seen_imports.add((module, line))
            imports.append(
                ImportRef(module=module, location=f"{rel_path}:{line}", scope=scope)
            )

    for match in _CALLSITE.finditer(cleaned):
        line = cleaned[: match.start()].count("\n") + 1
        callsites.append(
            CallsiteRef(name=match.group(1), location=f"{rel_path}:{line}", scope=scope)
        )

    return imports, callsites


def collect_js(
    entries,
) -> tuple[list[ImportRef], list[CallsiteRef]]:
    """Extract from every JS/TS entry in an inventory."""
    imports: list[ImportRef] = []
    callsites: list[CallsiteRef] = []
    for entry in entries:
        if entry.language not in JS_LANGUAGES or entry.is_binary:
            continue
        try:
            text = Path(entry.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        file_imports, file_calls = parse_js_source(text, entry.rel_path, entry.scope)
        imports.extend(file_imports)
        callsites.extend(file_calls)
    return imports, callsites


__all__ = ["JS_LANGUAGES", "collect_js", "parse_js_source"]
