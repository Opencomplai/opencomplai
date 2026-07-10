# Contributing to OpenComplai

Thank you for your interest in contributing! OpenComplai is an open-source project and we welcome contributions from everyone.

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

## Getting Started

### 1. [Development Setup](development-setup.md)
Set up your local development environment:
- Fork and clone the repository
- Install dependencies
- Set up pre-commit hooks
- Run tests locally

### 2. [Coding Standards](coding-standards.md)
Follow our code standards:
- Python: PEP 8 with type hints
- JavaScript: Prettier + ESLint
- Documentation: Markdown best practices
- Commit messages: Conventional commits

### 3. [Testing](testing.md)
Write and run tests:
- Unit tests with pytest (Python) / Jest (JS)
- Integration tests
- Coverage requirements
- CI/CD test pipeline

### 4. [Code Review](code-review.md)
Submit and review code:
- Create pull request
- Request code review
- Address feedback
- Merge to main

### 5. [Release Process](release-process.md)
How releases work:
- Semantic versioning
- Changelog updates
- Tag releases
- Publish packages

---

## Contribution Workflow

### 1. Fork & Clone

=== "macOS / Linux"
    ```bash
    # Fork the repository on GitHub

    # Clone your fork
    git clone https://github.com/YOUR_USERNAME/opencomplai.git
    cd opencomplai

    # Add upstream remote
    git remote add upstream https://github.com/Opencomplai/opencomplai.git
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Fork the repository on GitHub

    # Clone your fork
    git clone https://github.com/YOUR_USERNAME/opencomplai.git
    cd opencomplai

    # Add upstream remote
    git remote add upstream https://github.com/Opencomplai/opencomplai.git
    ```

### 2. Create Feature Branch

=== "macOS / Linux"
    ```bash
    # Update main
    git checkout main
    git pull upstream main

    # Create feature branch
    git checkout -b feature/short-description
    # or for bugs: bug/issue-number-description
    # or for docs: docs/description
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Update main
    git checkout main
    git pull upstream main

    # Create feature branch
    git checkout -b feature/short-description
    # or for bugs: bug/issue-number-description
    # or for docs: docs/description
    ```

### 3. Make Changes

=== "macOS / Linux"
    ```bash
    # Install development dependencies
    pip install -e ".[dev]"  # Python
    npm install              # JavaScript

    # Make your changes and test locally
    python -m pytest         # Run tests
    npm test                 # Run JS tests
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Install development dependencies
    pip install -e ".[dev]"  # Python
    npm install              # JavaScript

    # Make your changes and test locally
    python -m pytest         # Run tests
    npm test                 # Run JS tests
    ```

### 4. Commit Changes

=== "macOS / Linux"
    ```bash
    # Follow conventional commit format
    git add .
    git commit -m "feat: add new feature

    Optional longer description explaining the change.
    Closes #123"

    # Good commit messages:
    # feat: add document export to PDF
    # fix: handle rate limit errors correctly
    # docs: improve authentication guide
    # test: add test for document creation
    # refactor: simplify document processing
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Follow conventional commit format
    git add .
    git commit -m "feat: add new feature

    Optional longer description explaining the change.
    Closes #123"

    # Good commit messages:
    # feat: add document export to PDF
    # fix: handle rate limit errors correctly
    # docs: improve authentication guide
    # test: add test for document creation
    # refactor: simplify document processing
    ```

### 5. Push & Create PR

=== "macOS / Linux"
    ```bash
    # Push to your fork
    git push origin feature/short-description

    # Create pull request on GitHub
    # Fill in the PR template with:
    # - Description of changes
    # - Related issues (Closes #123)
    # - Screenshots (if UI changes)
    # - Test plan
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Push to your fork
    git push origin feature/short-description

    # Create pull request on GitHub
    # Fill in the PR template with:
    # - Description of changes
    # - Related issues (Closes #123)
    # - Screenshots (if UI changes)
    # - Test plan
    ```

### 6. Address Feedback

=== "macOS / Linux"
    ```bash
    # Make requested changes
    git add .
    git commit -m "refactor: address review feedback"
    git push origin feature/short-description

    # GitHub will update the PR automatically
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Make requested changes
    git add .
    git commit -m "refactor: address review feedback"
    git push origin feature/short-description

    # GitHub will update the PR automatically
    ```

### 7. Merge

Once approved:
- Maintainers will merge to main
- Your feature goes into next release
- You're now a contributor!

---

## Development Quick Start

### Python Development

=== "macOS / Linux"
    ```bash
    # Create virtual environment
    python -m venv venv
    source venv/bin/activate

    # Install dev dependencies
    pip install -e ".[dev]"

    # Run tests
    pytest

    # Run linters
    black .          # Format code
    mypy .           # Type checking
    ruff check .     # Linting

    # Build locally
    python -m build
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Create virtual environment
    python -m venv venv
    .\venv\Scripts\Activate.ps1

    # Install dev dependencies
    pip install -e ".[dev]"

    # Run tests
    pytest

    # Run linters
    black .          # Format code
    mypy .           # Type checking
    ruff check .     # Linting

    # Build locally
    python -m build
    ```

### JavaScript Development

=== "macOS / Linux"
    ```bash
    # Install dependencies
    npm install

    # Run tests
    npm test

    # Run linters
    npm run lint
    npm run format

    # Build
    npm run build
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Install dependencies
    npm install

    # Run tests
    npm test

    # Run linters
    npm run lint
    npm run format

    # Build
    npm run build
    ```

---

## Code Standards Summary

### Python
- Python 3.9+
- PEP 8 style (enforced by Black)
- Type hints required
- Docstrings for public functions
- Tests required for new features

### JavaScript
- TypeScript preferred
- Prettier formatting
- ESLint checks
- JSDoc comments
- Tests required for new features

### Documentation
- Markdown format
- Clear and concise
- Links to related docs
- Code examples
- Keep up to date

---

## Testing Requirements

### Coverage
- Minimum 80% code coverage
- New features require tests
- Bug fixes should include regression tests

### Test Files
```
src/            Source code
src/foo.py      Module
tests/
tests/test_foo.py  Test file (parallel structure)
```

### Running Tests

=== "macOS / Linux"
    ```bash
    # Python
    pytest                    # Run all
    pytest tests/test_foo.py  # Run specific file
    pytest -cov              # With coverage

    # JavaScript
    npm test                 # Run all
    npm test -- test_foo.js  # Run specific file
    npm test -- --coverage   # With coverage
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Python
    pytest                    # Run all
    pytest tests/test_foo.py  # Run specific file
    pytest -cov              # With coverage

    # JavaScript
    npm test                 # Run all
    npm test -- test_foo.js  # Run specific file
    npm test -- --coverage   # With coverage
    ```

---

## Pull Request Checklist

Before submitting a PR:

- [ ] Feature branch created from `main`
- [ ] Code follows style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] No breaking changes (or documented)
- [ ] Changelog updated (if applicable)
- [ ] Changes reviewed locally

---

## Community Guidelines

### Be Respectful
- Treat everyone with respect
- Assume good intentions
- Provide constructive feedback

### Be Helpful
- Help others learn
- Answer questions patiently
- Share knowledge

### Be Constructive
- Focus on ideas, not people
- Provide specific feedback
- Suggest improvements

### Be Inclusive
- Welcome diverse perspectives
- Be mindful of language
- Support new contributors

---

## Communication Channels

See **[Support & Community](../community/support.md)** for the full list of channels, GitHub issue templates, and security reporting.

- **Discord**: [Developer community](https://discord.gg/egjX5JgQJ) — EU AI Act workflows, pipeline integration, and closed-beta feedback
- **Issues**: [Bug](https://github.com/Opencomplai/opencomplai/issues/new?template=bug-report.yml), [feature](https://github.com/Opencomplai/opencomplai/issues/new?template=feature-request.yml), and [task](https://github.com/Opencomplai/opencomplai/issues/new?template=task.yml) templates
- **Discussions**: Ideas, questions, announcements
- **Pull Requests**: Code changes and reviews
- **Email**: open@opencomplai.com (for private concerns)

---

## Recognition

All contributors are recognized:
- In [CONTRIBUTORS.md](https://github.com/Opencomplai/opencomplai/blob/main/CONTRIBUTORS.md)
- In release notes
- On our website

---

## Getting Help

### Questions?
- [Developer Discord](https://discord.gg/egjX5JgQJ)
- [GitHub Discussions](https://github.com/Opencomplai/opencomplai/discussions)
- Check [Development Setup](development-setup.md)
- Email: open@opencomplai.com

### Issues?
- Search [existing issues](https://github.com/Opencomplai/opencomplai/issues)
- Check [Troubleshooting](../troubleshooting/index.md)
- Ask in [Discussions](https://github.com/Opencomplai/opencomplai/discussions) or on [Discord](https://discord.gg/egjX5JgQJ)

---

## Thank You!

Your contributions make OpenComplai better for everyone.

**Happy coding!**
