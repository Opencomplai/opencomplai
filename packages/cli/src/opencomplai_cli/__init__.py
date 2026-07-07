"""Opencomplai CLI."""

__version__ = "0.1.0"

# Canonical project metadata — single source of truth for the `--version`
# flag and the `opencomplai info` command. Mirrors the [project] table in
# each package's pyproject.toml so the CLI never depends on `pip show`.
PROJECT_NAME = "opencomplai"
PROJECT_TAGLINE = "Open-source AI compliance for a trustworthy future."
PROJECT_HOMEPAGE = "https://opencomplai.com"
PROJECT_DOCS_URL = "https://docs.opencomplai.com"
PROJECT_AUTHOR = "Opencomplai"
PROJECT_AUTHOR_EMAIL = "hello@opencomplai.com"
PROJECT_LICENSE = "AGPL-3.0-only"

# The three distributions that make up the Opencomplai suite, in dependency
# order (umbrella SDK → CLI → core engine), with a short role description.
SUITE_PACKAGES: tuple[tuple[str, str], ...] = (
    ("opencomplai", "SDK (umbrella)"),
    ("opencomplai-cli", "command-line interface"),
    ("opencomplai-core", "risk assessment engine"),
)
