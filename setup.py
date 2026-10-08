"""Make the repo root installable so pre-commit can set up the hook repository.

pre-commit runs ``pip install .`` on this repository for every ``language: python``
hook. The root is not a Python project, so this builds an empty distribution; the CLI
itself comes from the pinned ``additional_dependencies`` in ``.pre-commit-hooks.yaml``.
"""

from setuptools import setup

# Explicit empty lists switch off setuptools' flat-layout auto-discovery, which
# otherwise refuses the many top-level directories of this repository.
setup(
    name="opencomplai-pre-commit-hooks",
    version="0.0.0",
    packages=[],
    py_modules=[],
)
