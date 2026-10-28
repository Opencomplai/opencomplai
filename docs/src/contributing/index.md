# Contributing to OpenComplai

Thank you for your interest in contributing! OpenComplai is an open-source project and we welcome contributions from everyone.

!!! note "One set of rules"
    The rules for contributing (branch names, commit format, the DCO sign-off, the CLA, what we expect in a pull request, and what happens after you open one) live in one place: [CONTRIBUTING.md](https://github.com/Opencomplai/opencomplai/blob/main/CONTRIBUTING.md) in the repository. This page is the map of the guides in this section.

## Ways to Contribute

### Report Bugs
Found a bug? [Open an issue](https://github.com/Opencomplai/opencomplai/issues/new?template=bug-report.yml) with:
- Description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python/Node version)

### Suggest Features
Have an idea? [Open a discussion](https://github.com/Opencomplai/opencomplai/discussions/new?category=ideas) or create an issue with:
- Use case and motivation
- Proposed solution
- Alternative solutions considered

### Write Documentation
- Fix typos or improve clarity
- Add examples or tutorials
- Improve API documentation
- Translate to other languages (planned)

### Submit Code
- Bug fixes
- New features
- Performance improvements
- Refactoring

### Write Tests
- Unit tests
- Integration tests
- End-to-end tests
- Test coverage improvements

### Improve Design
- UI/UX improvements
- Accessibility enhancements
- Performance optimizations
- Architecture improvements

---

## JS/TS repository scanning (regex extractor; real parser is a design spike)

`opencomplai scan` extracts imports and model-call sites from `.js`, `.jsx`, `.ts` and
`.tsx` files with a regex extractor (static `import`, `export ... from`, literal
`require()` and `import()`). Computed imports are invisible, and it is not a parser. A
design spike for a real parser exists at `docs/design/js-ts-scanning-spike.md` — it
documents an architecture direction, not a shipped feature. If you're interested in
contributing the parser work, start there.

---

## Start here

Your first pull request, step by step, is section 2 of [CONTRIBUTING.md](https://github.com/Opencomplai/opencomplai/blob/main/CONTRIBUTING.md). The guides in this section go deeper:

1. **[Development Setup](development-setup.md)**: fork and clone, install dependencies, set up pre-commit hooks, run tests locally
2. **[Coding Standards](coding-standards.md)**: the style and typing conventions
3. **[Testing](testing.md)**: unit and integration tests, coverage, the CI pipeline
4. **[Code Review](code-review.md)**: opening a pull request, requesting review, addressing feedback
5. **[Release Process](release-process.md)**: how releases work
6. **[Adding Rules](adding-rules.md)** and **[Adding Framework Packs](adding-framework-packs.md)**: extending the engine

Linting and formatting use `ruff`; Node.js code in `services/gateway-api` uses `pnpm lint` and `pnpm format:check`. See CONTRIBUTING.md for the exact commands and for the branch and commit conventions.

---

## Community

See **[Support & Community](../community/support.md)** for the full list of channels, the GitHub issue forms, and how to report a security vulnerability. Questions and ideas belong in [GitHub Discussions](https://github.com/Opencomplai/opencomplai/discussions); the [Developer Discord](https://discord.gg/egjX5JgQJ) is the quick-chat room. We aim for a first reply within 48 hours on working days.

Be respectful, assume good intentions, give specific and constructive feedback, welcome new contributors and diverse perspectives.

## Recognition

Every change that ships is credited in the release notes and in the [changelog](https://github.com/Opencomplai/opencomplai/blob/main/CHANGELOG.md). [GOVERNANCE.md](https://github.com/Opencomplai/opencomplai/blob/main/GOVERNANCE.md) describes how contributors grow into triage and review roles.

## Getting Help

- [GitHub Discussions](https://github.com/Opencomplai/opencomplai/discussions) and the [Developer Discord](https://discord.gg/egjX5JgQJ)
- [Development Setup](development-setup.md) and [Troubleshooting](../troubleshooting/index.md)
- Search [existing issues](https://github.com/Opencomplai/opencomplai/issues) first
- Email: open@opencomplai.com (for private concerns)

Thank you for helping make OpenComplai better for everyone.
