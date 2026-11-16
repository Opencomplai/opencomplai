# Homebrew formula

`opencomplai.rb` is the template for the Homebrew formula of the `opencomplai` CLI. The published
copy lives in the tap `Opencomplai/homebrew-tap` at `Formula/opencomplai.rb`, and users run
`brew install Opencomplai/tap/opencomplai` (the same as `brew tap Opencomplai/tap` followed by
`brew install opencomplai`).

**Status (8 Nov 2026):** the tap exists and carries the 0.15.0 formula with its dependency
`resource` blocks. This template keeps the placeholder `sha256` and no resource blocks, because each
release patches a copy of it, so the tree never holds a stale hash. The 0.15.0 formula was built and
tested on Linux only, with Homebrew 7.0.12 in the `homebrew/brew` image: `brew install`, `brew test`,
`brew style` and `brew audit --strict --new` on the tap formula (commit `70da9cb`), and a real
`brew tap Opencomplai/tap` followed by a plain `brew install Opencomplai/tap/opencomplai` from GitHub.
macOS has not been tested, and the install page of the docs still calls the tap "planned" until the
maintainers decide to announce it (see the release process).

## Lint

Offline (no brew needed): `packages/cli/tests/test_homebrew_formula.py`
checks the structure: first line `# frozen_string_literal: true`, class,
`include Language::Python::Virtualenv`, `homepage`, `url`, a 64-hex `sha256`,
`license`, `depends_on "python@3.N"`, `virtualenv_install_with_resources`, a
`test do` block running `opencomplai --version`, no tabs, no trailing whitespace,
one final newline, and a `desc` under 80 characters with no leading article, no
trailing period and not starting with the formula name. It also checks that the
licence and Python floor match the package metadata and that the formula version is at
least the package version. `test_homebrew_release_script.py` and `test_homebrew_resources.py`
guard `scripts/homebrew-release.sh` and `resources.py`.

With Homebrew (the offline tests only guard the common rules), inside the container described below:

```bash
brew style Opencomplai/tap/opencomplai
brew audit --strict --new Opencomplai/tap/opencomplai
```

## Per release

1. The release bump moves the version in `url`.
2. Once the release is on PyPI, copy the template and run
   `bash scripts/homebrew-release.sh X.Y.Z --formula <copy>`. It checks the PyPI digest and the
   download, then sets the hashed PyPI source `url` (the form `brew audit` wants) and `sha256` in the copy.
3. Add the dependency `resource` blocks. `brew update-python-resources` only considers releases
   uploaded more than 24 hours ago (it runs pip with `--uploaded-prior-to=P1D`), and our own
   `opencomplai-cli` and `opencomplai-core` are new on release day, so that day it stops with
   "Unable to determine dependencies" (pip underneath says no matching distribution; it was seen for
   0.15.0). `--ignore-main-package-cooldown` does not help, because those two are dependencies of the main
   package and still respect the cooldown. Either run `brew update-python-resources` the next day (not
   yet exercised on this formula), or use the formula's Python (3.12) for
   `python -m pip install --dry-run --ignore-installed --report report.json opencomplai==X.Y.Z` and then
   `python packaging/homebrew/resources.py report.json <copy>`. The script writes the same blocks and refuses
   any third-party package under 24 hours old, so the protection of the rule stays; 0.15.0 was done this way.
4. Build and test in a throwaway container, with no sudo and nothing installed on the machine:
   `docker run --rm -it homebrew/brew`. The image can carry a year-old Homebrew that fails on current
   bottles, so run `brew update` first. Put the formula in a git tap (`brew tap local/proof <git dir>`) and
   run `brew trust --tap local/proof`, which `brew update-python-resources` needs on a local tap. Then run
   `brew style`, `brew audit --strict --new`, `brew install --build-from-source`, `brew test`, and a real
   `opencomplai check -m system-manifest.json` in `examples/gate-demo/prohibited` (exit 3). Running
   `brew install` on a named formula from a tap trusts that formula by itself.
5. Copy the formula to `Formula/opencomplai.rb` in the tap and push it. Then, in a clean container, run
   `brew tap Opencomplai/tap` and a plain `brew install Opencomplai/tap/opencomplai` once, and `brew test` it.

## What the formula needs, and why

- `rust` (build): pydantic-core and cryptography are built from source (every Python resource is, with
  `--no-binary`).
- `jpeg-turbo`: Pillow, pulled in by the PDF report support in `fpdf2`, would not build without it.
- `zlib`, declared with `uses_from_macos` as homebrew-core does for Pillow. The 0.15.0 build did not show
  that it is needed on Linux, where `python@3.12` already brings in a zlib.
- `libffi`, `libyaml`, `openssl@3`: cffi, PyYAML and cryptography.
- The explicit `bin.install_symlink` in `install`: `opencomplai-cli`, a resource, installs the same
  `opencomplai` script before the package does, so Homebrew's helper does not see it as new and links
  nothing. Without the symlink the formula installs but `opencomplai` is not on the PATH.
- The two CI connector scripts that come with `opencomplai-cli` (`opencomplai-gha-connector`,
  `opencomplai-gitlab-connector`) are installed inside the formula's virtualenv but not linked onto the PATH.
